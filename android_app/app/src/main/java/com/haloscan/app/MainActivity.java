package com.haloscan.app;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.print.PrintAttributes;
import android.print.PrintManager;
import android.provider.MediaStore;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.window.OnBackInvokedCallback;
import android.window.OnBackInvokedDispatcher;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.RequiresApi;
import androidx.core.content.FileProvider;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * Halo Scan in a WebView: the same role-based web app the server serves to browsers, plus
 * native camera capture for samples, Android printing for reports, and a clear screen when the
 * server can't be reached.
 */
public class MainActivity extends Activity {
    private static final int REQ_PHOTO = 1;
    private static final int REQ_VIDEO = 2;
    private static final int REQ_FILE = 3;
    private static final int REQ_CAMERA_FOR_CAPTURE = 10;
    private static final int REQ_CAMERA_FOR_PAGE = 11;
    private static final int VIDEO_SECONDS = 10;

    private String serverUrl;
    private WebView web;
    private ProgressBar progress;
    private View errorPanel;
    private boolean mainFrameFailed;

    private ValueCallback<Uri[]> fileCallback;
    private WebChromeClient.FileChooserParams chooserParams;
    private File captureFile;
    private Uri captureUri;
    private int pendingCaptureKind;
    private PermissionRequest pendingPagePermission;
    private Object backCallback;  // OnBackInvokedCallback on Android 13+

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        serverUrl = ServerConfig.load(this);
        if (serverUrl == null) {
            openSetup();
            return;
        }

        setContentView(R.layout.activity_main);
        EdgeToEdge.apply(this, findViewById(R.id.main_root));
        web = findViewById(R.id.web);
        progress = findViewById(R.id.progress);
        errorPanel = findViewById(R.id.error_panel);
        ((TextView) findViewById(R.id.error_address)).setText(serverUrl);
        findViewById(R.id.retry).setOnClickListener(v -> loadApp());
        findViewById(R.id.change_server).setOnClickListener(v -> openSetup());

        Captures.clear(this);
        configureWebView();

        if (savedInstanceState == null || web.restoreState(savedInstanceState) == null) loadApp();
        updateBackHandling();
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        if (web != null) web.saveState(outState);
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
            Captures.clear(this);
        }
        super.onDestroy();
    }

    /** Only reached on Android 12 and older; Android 13+ uses {@link #updateBackHandling()}. */
    @Override
    @SuppressLint("GestureBackNavigation")
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        handleBack();
    }

    private void handleBack() {
        if (errorPanel.getVisibility() != View.VISIBLE && web.canGoBack()) web.goBack();
        else finish();
    }

    /**
     * Android 13+: intercept back only while there is a page to go back to, so at the first page
     * the system's own predictive "back to home" gesture and animation apply.
     */
    private void updateBackHandling() {
        if (Build.VERSION.SDK_INT < 33) return;
        boolean intercept = errorPanel.getVisibility() != View.VISIBLE && web.canGoBack();
        if (intercept && backCallback == null) {
            backCallback = BackApi33.register(this, this::handleBack);
        } else if (!intercept && backCallback != null) {
            BackApi33.unregister(this, backCallback);
            backCallback = null;
        }
    }

    @RequiresApi(33)
    private static final class BackApi33 {
        static Object register(Activity activity, Runnable onBack) {
            OnBackInvokedCallback callback = onBack::run;
            activity.getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    OnBackInvokedDispatcher.PRIORITY_DEFAULT, callback);
            return callback;
        }

        static void unregister(Activity activity, Object callback) {
            activity.getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback((OnBackInvokedCallback) callback);
        }
    }

    private void openSetup() {
        startActivity(new Intent(this, SetupActivity.class));
        finish();
    }

    private void loadApp() {
        mainFrameFailed = false;
        errorPanel.setVisibility(View.GONE);
        web.setVisibility(View.VISIBLE);
        web.loadUrl(serverUrl + "/");
        updateBackHandling();
    }

    private void showError() {
        mainFrameFailed = true;
        web.stopLoading();
        web.setVisibility(View.INVISIBLE);
        progress.setVisibility(View.GONE);
        errorPanel.setVisibility(View.VISIBLE);
        updateBackHandling();
    }

    // ---------------------------------------------------------------- WebView

    private void configureWebView() {
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setUserAgentString(s.getUserAgentString() + " HaloScanAndroid/1.0");
        WebView.setWebContentsDebuggingEnabled((getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0);

        // The web app's "Print / save PDF report" button calls window.print(), which a WebView
        // ignores; route it to Android printing (which also offers "Save as PDF").
        web.addJavascriptInterface(new PrintBridge(), "HaloScanAndroid");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri url = request.getUrl();
                if (ServerConfig.sameOrigin(serverUrl, url)) return false;
                try {  // Anything outside the Halo Scan server opens in the phone's browser.
                    startActivity(new Intent(Intent.ACTION_VIEW, url));
                } catch (ActivityNotFoundException ignored) {
                }
                return true;
            }

            @Override
            public void doUpdateVisitedHistory(WebView view, String url, boolean isReload) {
                updateBackHandling();
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                progress.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progress.setVisibility(View.GONE);
                if (!mainFrameFailed) {
                    view.evaluateJavascript("window.print=function(){HaloScanAndroid.print();};", null);
                }
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) showError();
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progress.setProgress(newProgress);
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                deliverFiles(null);  // a chooser that was still open is cancelled
                fileCallback = callback;
                chooserParams = params;
                showSampleChooser(params);
                return true;
            }

            @Override
            public void onPermissionRequest(PermissionRequest request) {
                // Live camera in the page (only possible when the server uses HTTPS).
                runOnUiThread(() -> handlePagePermission(request));
            }

            @Override
            public void onPermissionRequestCanceled(PermissionRequest request) {
                if (request == pendingPagePermission) pendingPagePermission = null;
            }
        });
    }

    public final class PrintBridge {
        @JavascriptInterface
        public void print() {
            runOnUiThread(() -> {
                PrintManager pm = getSystemService(PrintManager.class);
                if (pm == null) return;
                pm.print(getString(R.string.print_job),
                        web.createPrintDocumentAdapter(getString(R.string.print_job)),
                        new PrintAttributes.Builder().build());
            });
        }
    }

    // ---------------------------------------------------------------- sample capture

    private void showSampleChooser(WebChromeClient.FileChooserParams params) {
        boolean images = accepts(params, "image/");
        boolean videos = accepts(params, "video/");
        List<String> labels = new ArrayList<>();
        List<Integer> actions = new ArrayList<>();
        if (images) { labels.add(getString(R.string.chooser_photo)); actions.add(REQ_PHOTO); }
        if (videos) { labels.add(getString(R.string.chooser_video)); actions.add(REQ_VIDEO); }
        labels.add(getString(R.string.chooser_file));
        actions.add(REQ_FILE);

        new AlertDialog.Builder(this)
                .setTitle(R.string.chooser_title)
                .setItems(labels.toArray(new String[0]), (dialog, which) -> {
                    int action = actions.get(which);
                    if (action == REQ_FILE) openFilePicker();
                    else startCapture(action);
                })
                .setOnCancelListener(dialog -> deliverFiles(null))
                .show();
    }

    private static boolean accepts(WebChromeClient.FileChooserParams params, String prefix) {
        String[] types = params.getAcceptTypes();
        if (types == null || types.length == 0) return true;
        for (String t : types) {
            if (t == null || t.isEmpty() || t.startsWith(prefix) || t.equals("*/*")) return true;
        }
        return false;
    }

    private void openFilePicker() {
        try {
            startActivityForResult(chooserParams.createIntent(), REQ_FILE);
        } catch (ActivityNotFoundException e) {
            deliverFiles(null);
        }
    }

    private void startCapture(int kind) {
        if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            pendingCaptureKind = kind;
            requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAMERA_FOR_CAPTURE);
            return;
        }
        boolean photo = kind == REQ_PHOTO;
        captureFile = Captures.newFile(this, photo ? ".jpg" : ".mp4");
        captureUri = FileProvider.getUriForFile(this, getPackageName() + ".captures", captureFile);

        Intent intent = new Intent(photo ? MediaStore.ACTION_IMAGE_CAPTURE : MediaStore.ACTION_VIDEO_CAPTURE);
        intent.putExtra(MediaStore.EXTRA_OUTPUT, captureUri);
        intent.setClipData(ClipData.newRawUri("", captureUri));
        intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
        if (!photo) {
            intent.putExtra(MediaStore.EXTRA_DURATION_LIMIT, VIDEO_SECONDS);
            intent.putExtra(MediaStore.EXTRA_VIDEO_QUALITY, 1);
        }
        try {
            startActivityForResult(intent, kind);
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, R.string.no_camera_app, Toast.LENGTH_LONG).show();
            deliverFiles(null);
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_FILE) {
            deliverFiles(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
        } else if (requestCode == REQ_PHOTO || requestCode == REQ_VIDEO) {
            Uri result = null;
            if (resultCode == RESULT_OK) {
                if (captureFile != null && captureFile.length() > 0) result = captureUri;
                else if (data != null && data.getData() != null) result = data.getData();  // camera ignored EXTRA_OUTPUT
            }
            deliverFiles(result == null ? null : new Uri[]{result});
        }
    }

    private void deliverFiles(Uri[] files) {
        if (fileCallback != null) {
            fileCallback.onReceiveValue(files);
            fileCallback = null;
        }
    }

    // ---------------------------------------------------------------- permissions

    private void handlePagePermission(PermissionRequest request) {
        if (!ServerConfig.sameOrigin(serverUrl, request.getOrigin())) {
            request.deny();
            return;
        }
        boolean wantsCamera = false;
        for (String r : request.getResources()) {
            if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(r)) wantsCamera = true;
        }
        if (!wantsCamera) {
            request.deny();
        } else if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            request.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
        } else {
            pendingPagePermission = request;
            requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAMERA_FOR_PAGE);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
        if (requestCode == REQ_CAMERA_FOR_CAPTURE) {
            if (granted) {
                startCapture(pendingCaptureKind);
            } else {
                Toast.makeText(this, R.string.camera_denied, Toast.LENGTH_LONG).show();
                deliverFiles(null);
            }
        } else if (requestCode == REQ_CAMERA_FOR_PAGE && pendingPagePermission != null) {
            if (granted) pendingPagePermission.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
            else pendingPagePermission.deny();
            pendingPagePermission = null;
        }
    }
}

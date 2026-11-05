package com.haloscan.app;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;

/** Asks for the server address once, checks it really is a Halo Scan server, then saves it. */
public class SetupActivity extends Activity {
    private EditText urlField;
    private TextView status;
    private Button connect;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_setup);
        EdgeToEdge.apply(this, findViewById(R.id.setup_root));

        urlField = findViewById(R.id.server_url);
        status = findViewById(R.id.setup_status);
        connect = findViewById(R.id.connect);

        String saved = ServerConfig.load(this);
        urlField.setText(saved != null ? saved : "http://");
        urlField.setSelection(urlField.getText().length());

        connect.setOnClickListener(v -> tryConnect());
        urlField.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_GO) {
                tryConnect();
                return true;
            }
            return false;
        });
    }

    private void tryConnect() {
        String url = ServerConfig.normalize(urlField.getText().toString());
        if (url == null) {
            showStatus(getString(R.string.setup_bad_url), true);
            return;
        }
        connect.setEnabled(false);
        showStatus(getString(R.string.setup_checking), false);
        new Thread(() -> {
            boolean ok = ServerConfig.isReachable(url);
            runOnUiThread(() -> {
                if (isFinishing() || isDestroyed()) return;
                connect.setEnabled(true);
                if (!ok) {
                    showStatus(getString(R.string.setup_unreachable), true);
                    return;
                }
                ServerConfig.save(this, url);
                startActivity(new Intent(this, MainActivity.class)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
                finish();
            });
        }, "server-check").start();
    }

    private void showStatus(String message, boolean isError) {
        status.setText(message);
        status.setTextColor(getColor(isError ? R.color.danger : R.color.ink_muted));
        status.setVisibility(View.VISIBLE);
    }
}

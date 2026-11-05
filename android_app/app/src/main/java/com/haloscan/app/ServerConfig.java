package com.haloscan.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.regex.Pattern;

/** The address of the Halo Scan server (the FastAPI backend that also serves the web app). */
final class ServerConfig {
    private static final String PREFS = "server";
    private static final String KEY_URL = "url";
    private static final Pattern HEALTH_OK = Pattern.compile("\"status\"\\s*:\\s*\"ok\"");

    private ServerConfig() {}

    static String load(Context context) {
        return prefs(context).getString(KEY_URL, null);
    }

    static void save(Context context, String url) {
        prefs(context).edit().putString(KEY_URL, url).apply();
    }

    /** "192.168.1.20:8001" -> "http://192.168.1.20:8001"; null if it isn't an http(s) address. */
    static String normalize(String input) {
        if (input == null) return null;
        String url = input.trim();
        if (url.isEmpty()) return null;
        if (!url.contains("://")) url = "http://" + url;
        while (url.endsWith("/")) url = url.substring(0, url.length() - 1);
        Uri uri = Uri.parse(url);
        String scheme = uri.getScheme() == null ? "" : uri.getScheme().toLowerCase(Locale.ROOT);
        if (!scheme.equals("http") && !scheme.equals("https")) return null;
        if (uri.getHost() == null || uri.getHost().isEmpty()) return null;
        return url;
    }

    /** True when the address answers /api/health like a Halo Scan server. Call off the UI thread. */
    static boolean isReachable(String url) {
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(url + "/api/health").openConnection();
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(5000);
            if (conn.getResponseCode() != 200) return false;
            StringBuilder body = new StringBuilder();
            try (BufferedReader in = new BufferedReader(
                    new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = in.readLine()) != null && body.length() < 4096) body.append(line);
            }
            return HEALTH_OK.matcher(body).find();
        } catch (Exception e) {
            return false;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    /** Same scheme, host and port as the configured server. */
    static boolean sameOrigin(String serverUrl, Uri other) {
        if (serverUrl == null || other == null) return false;
        Uri server = Uri.parse(serverUrl);
        String a = server.getScheme(), b = other.getScheme();
        return a != null && a.equalsIgnoreCase(b)
                && server.getHost() != null && server.getHost().equalsIgnoreCase(other.getHost())
                && port(server) == port(other);
    }

    private static int port(Uri uri) {
        if (uri.getPort() != -1) return uri.getPort();
        return "https".equalsIgnoreCase(uri.getScheme()) ? 443 : 80;
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}

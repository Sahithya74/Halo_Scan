package com.haloscan.app;

import android.content.Context;

import java.io.File;

/**
 * Sample photos/videos taken in the app live only in its private cache and are deleted on the
 * next capture and when the app closes — like the server, the phone keeps no sample images.
 */
final class Captures {
    private Captures() {}

    static File newFile(Context context, String extension) {
        clear(context);
        File dir = dir(context);
        //noinspection ResultOfMethodCallIgnored
        dir.mkdirs();
        return new File(dir, "sample_" + System.currentTimeMillis() + extension);
    }

    static void clear(Context context) {
        File[] files = dir(context).listFiles();
        if (files == null) return;
        for (File f : files) {
            //noinspection ResultOfMethodCallIgnored
            f.delete();
        }
    }

    private static File dir(Context context) {
        return new File(context.getCacheDir(), "captures");
    }
}

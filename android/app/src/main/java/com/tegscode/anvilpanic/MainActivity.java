package com.tegscode.anvilpanic;

import android.app.Activity;
import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.Build;
import android.os.Bundle;
import android.view.Surface;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/**
 * One WebView, one local HTML file, one accelerometer. No AndroidX, no network
 * permission, no ads, no telemetry.
 *
 * The game itself is untouched. It already answers to ArrowLeft/ArrowRight and
 * ShiftLeft, and it already turns pointer-down-and-hold into "walk towards my
 * finger", so this shell only has to supply:
 *
 *   - on-screen buttons  -> synthetic keyboard events
 *   - tilt               -> accelerometer, also synthetic keyboard events
 *   - touch              -> nothing, the game does it natively
 *
 * Everything visual (pads, mode chip) is injected from assets/overlay.js, which
 * keeps the Java side to wiring and makes the controls tweakable without a
 * recompile of the game.
 */
public class MainActivity extends Activity implements SensorEventListener {

    private WebView web;
    private SensorManager sensors;

    /** overlay.js, read once from assets and injected after each page load. */
    private String overlaySource = "";

    /** Baseline tilt captured when the sensor starts, so "level" is where the phone is. */
    private float baseX = Float.NaN;
    private int tiltDir = 0;

    private static final float DEADZONE = 1.2f;   // m/s^2 before a lean counts
    private static final float GAIN = 2.2f;       // lean -> usable range

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(true);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setTextZoom(100);
        s.setUseWideViewPort(false);
        s.setLoadWithOverviewMode(false);
        s.setCacheMode(WebSettings.LOAD_NO_CACHE);

        web.setBackgroundColor(0xFF151020);
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
        web.setLongClickable(false);
        web.setHapticFeedbackEnabled(false);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                // Overlay is injected after load so it can rely on document.body
                // and on the game's own listeners being installed.
                view.evaluateJavascript(overlaySource, null);
            }
        });
        web.setWebChromeClient(new WebChromeClient());
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            WebView.setWebContentsDebuggingEnabled(false);
        }

        setContentView(web);
        hideSystemBars();
        overlaySource = readAsset("overlay.js");
        web.loadUrl("file:///android_asset/index.html");

        sensors = (SensorManager) getSystemService(Context.SENSOR_SERVICE);
    }

    // ------------------------------------------------------------------ chrome
    private void hideSystemBars() {
        View decor = getWindow().getDecorView();
        decor.setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            WindowInsetsController c = getWindow().getInsetsController();
            if (c != null) {
                c.hide(WindowInsets.Type.systemBars());
                c.setSystemBarsBehavior(
                        WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) hideSystemBars();
    }

    // ------------------------------------------------------------------- web
    private void js(String code) {
        if (web != null) web.evaluateJavascript(code, null);
    }

    private String readAsset(String name) {
        try (InputStream in = getAssets().open(name)) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            return new String(out.toByteArray(), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return "/* overlay missing: " + e.getMessage() + " */";
        }
    }

    // ------------------------------------------------------------------ tilt
    @Override
    protected void onResume() {
        super.onResume();
        if (web != null) web.onResume();
        baseX = Float.NaN;
        Sensor acc = sensors == null ? null : sensors.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
        if (acc != null) {
            sensors.registerListener(this, acc, SensorManager.SENSOR_DELAY_GAME);
        }
    }

    @Override
    protected void onPause() {
        if (sensors != null) sensors.unregisterListener(this);
        if (web != null) web.onPause();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.loadUrl("about:blank");
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }

    @Override
    public void onSensorChanged(SensorEvent e) {
        if (e.sensor.getType() != Sensor.TYPE_ACCELEROMETER) return;

        // In landscape the screen's left-right axis is the device's x axis; a
        // 180/270 rotation runs it the other way, so the sign flips.
        float x = e.values[0];
        int rot = getWindowManager().getDefaultDisplay().getRotation();
        if (rot == Surface.ROTATION_90 || rot == Surface.ROTATION_180) x = -x;

        if (Float.isNaN(baseX)) {
            baseX = x;   // calibrate to however the player is holding it
            return;
        }
        float d = (x - baseX) * GAIN;
        int dir = d > DEADZONE ? 1 : d < -DEADZONE ? -1 : 0;
        if (dir != tiltDir) {
            tiltDir = dir;
            js("window.__ap && window.__ap.tilt(" + dir + ")");
        }
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
        // nothing: an accelerometer without a magnetometer has no heading to track
    }
}

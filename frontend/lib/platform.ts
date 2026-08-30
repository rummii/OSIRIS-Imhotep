/**
 * Platform & environment detection utilities.
 *
 * Used to detect iOS WebView (Median.co / native UIWebView / WKWebView)
 * so we can show a helpful banner and disable features that require
 * native browser APIs (camera, microphone, Web Speech).
 */

/** True when running inside any iOS WebView (not in the standalone browser). */
export function isIOSWebView(): boolean {
  if (typeof navigator === "undefined") return false;
  // iOS WebView / Median / Capacitor / Cordova typically:
  //   - have no getUserMedia on navigator.mediaDevices
  //   - are on an iOS device (userAgent or platform check)
  // We check the feature availability as the most reliable signal.
  const w = window as unknown as {
    webkit?: { messageHandlers?: Record<string, unknown> };
    navigator?: { mediaDevices?: { getUserMedia?: unknown } };
  };
  const hasGetUserMedia = !!w.navigator?.mediaDevices?.getUserMedia;
  if (hasGetUserMedia) return false; // real browser

  const ua = navigator.userAgent ?? "";
  const platform = navigator.platform ?? "";
  const isIOS = platform.startsWith("iP") || /\biPhone|iPad|iPod\b/.test(ua);
  if (!isIOS) return false;

  // WKWebView / UIWebView do NOT expose SpeechRecognition either.
  // Check for the Median bridge as well.
  return !!(w.webkit?.messageHandlers?.osirisBridge);
}

/** True when the app is running in standalone / add-to-homescreen mode. */
export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia?.("(display-mode: standalone)").matches === true ||
    (window.navigator as unknown as { standalone?: boolean }).standalone === true
  );
}

/** True when the browser natively supports Web Speech API. */
export function isSpeechSupported(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as {
    SpeechRecognition?: unknown;
    webkitSpeechRecognition?: unknown;
  };
  return !!(w.SpeechRecognition ?? w.webkitSpeechRecognition);
}

/** True when the browser natively supports getUserMedia (camera / mic). */
export function isCameraSupported(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as { navigator?: { mediaDevices?: { getUserMedia?: unknown } } };
  return !!w.navigator?.mediaDevices?.getUserMedia;
}

/**
 * Inject the Median.co OSIRIS bridge postMessage sender.
 *
 * Returns null if not running inside the Median WebView context.
 *
 * Usage:
 *   const send = getMedianBridge();
 *   if (send) send({ type: "openUrl", url: "osiris://sow/123" });
 */
export function getMedianBridge(): ((msg: object) => void) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { webkit?: { messageHandlers?: { osirisBridge?: { postMessage: (msg: object) => void } } } };
  const handler = w.webkit?.messageHandlers?.osirisBridge;
  if (!handler) return null;
  return (msg: object) => {
    try { handler.postMessage(msg); } catch { /* ignore */ }
  };
}

package com.mediadownloader.hub.mobile

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.media.MediaScannerConnection
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.Handler
import android.os.Looper
import com.yausername.ffmpeg.FFmpeg
import com.yausername.youtubedl_android.YoutubeDL
import com.yausername.youtubedl_android.YoutubeDLRequest
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.util.UUID
import java.util.concurrent.Executors

/**
 * Native side of the app: runs yt-dlp on the phone (youtubedl-android) and
 * hands links to Flutter from mdhub:// links (website) and the Share menu.
 */
class MainActivity : FlutterActivity() {

    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private var events: EventChannel.EventSink? = null
    private var methods: MethodChannel? = null
    private var initialLink: Map<String, String>? = null
    @Volatile private var ready = false
    @Volatile private var currentProcess: String? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        val messenger = flutterEngine.dartExecutor.binaryMessenger

        EventChannel(messenger, "mdhub/progress").setStreamHandler(object : EventChannel.StreamHandler {
            override fun onListen(arguments: Any?, sink: EventChannel.EventSink?) { events = sink }
            override fun onCancel(arguments: Any?) { events = null }
        })

        methods = MethodChannel(messenger, "mdhub/downloader").also { channel ->
            channel.setMethodCallHandler { call, result ->
                when (call.method) {
                    "init" -> initEngine(result)
                    "initialLink" -> { result.success(initialLink); initialLink = null }
                    "download" -> {
                        val url = call.argument<String>("url") ?: ""
                        val format = call.argument<String>("format") ?: "best"
                        startDownload(url, format, result)
                    }
                    "cancel" -> {
                        val id = currentProcess
                        result.success(if (id != null) YoutubeDL.getInstance().destroyProcessById(id) else false)
                    }
                    "update" -> worker.execute {
                        try {
                            val status = YoutubeDL.getInstance().updateYoutubeDL(applicationContext, YoutubeDL.UpdateChannel.STABLE)
                            post { result.success(status?.name ?: "UNKNOWN") }
                        } catch (e: Exception) {
                            post { result.error("update", e.message, null) }
                        }
                    }
                    "version" -> result.success(YoutubeDL.getInstance().versionName(applicationContext))
                    else -> result.notImplemented()
                }
            }
        }

        initialLink = linkFromIntent(intent)
        requestLegacyStoragePermission()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        linkFromIntent(intent)?.let { methods?.invokeMethod("onLink", it) }
    }

    // ---------------------------------------------------------------- links

    /** mdhub://download?url=...&format=... from the website, or text shared from another app. */
    private fun linkFromIntent(intent: Intent?): Map<String, String>? {
        if (intent == null) return null
        if (intent.action == Intent.ACTION_VIEW) {
            val data: Uri = intent.data ?: return null
            if (data.scheme != "mdhub") return null
            val url = data.getQueryParameter("url") ?: return null
            if (!isWebUrl(url)) return null
            val format = data.getQueryParameter("format")?.takeIf { it in FORMATS } ?: "best"
            return mapOf("url" to url, "format" to format, "source" to "site")
        }
        if (intent.action == Intent.ACTION_SEND && intent.type == "text/plain") {
            val text = intent.getStringExtra(Intent.EXTRA_TEXT) ?: return null
            val url = Regex("https?://\\S+").find(text)?.value ?: return null
            return mapOf("url" to url, "format" to "best", "source" to "share")
        }
        return null
    }

    private fun isWebUrl(url: String): Boolean {
        val u = Uri.parse(url)
        return (u.scheme == "http" || u.scheme == "https") && !u.host.isNullOrEmpty() && url.length <= 2048
    }

    // ---------------------------------------------------------------- engine

    private fun initEngine(result: MethodChannel.Result) {
        if (ready) { result.success(true); return }
        worker.execute {
            try {
                // First start unpacks Python + yt-dlp + FFmpeg (a few seconds)
                YoutubeDL.getInstance().init(applicationContext)
                FFmpeg.getInstance().init(applicationContext)
                ready = true
                post { result.success(true) }
            } catch (e: Exception) {
                post { result.error("init", e.message ?: "Başlatılamadı", null) }
            }
        }
    }

    private fun outputDir(): File {
        val dir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "Medya İndir")
        dir.mkdirs()
        return dir
    }

    private fun startDownload(url: String, format: String, result: MethodChannel.Result) {
        if (!ready) { result.error("not_ready", "Uygulama henüz hazırlanıyor, birkaç saniye bekle.", null); return }
        if (!isWebUrl(url)) { result.error("bad_url", "Geçerli bir video bağlantısı gir.", null); return }
        if (currentProcess != null) { result.error("busy", "Bir indirme zaten sürüyor.", null); return }

        val id = UUID.randomUUID().toString()
        currentProcess = id
        result.success(id)

        worker.execute {
            val dir = outputDir()
            val request = YoutubeDLRequest(url).apply {
                addOption("--no-playlist")
                addOption("--no-mtime")
                addOption("-o", "${dir.absolutePath}/%(title).120B.%(ext)s")
                addOption("--restrict-filenames")
                // print the final path so we can show and index the file
                addOption("--print", "after_move:filepath")
                when (format) {
                    "mp3" -> { addOption("-f", "bestaudio/best"); addOption("-x"); addOption("--audio-format", "mp3"); addOption("--audio-quality", "192K") }
                    "720p" -> { addOption("-f", "bv*[height<=720]+ba/b[height<=720]/b"); addOption("--merge-output-format", "mp4") }
                    "480p" -> { addOption("-f", "bv*[height<=480]+ba/b[height<=480]/b"); addOption("--merge-output-format", "mp4") }
                    else -> { addOption("-f", "bv*[height<=1080]+ba/b[height<=1080]/b"); addOption("--merge-output-format", "mp4") }
                }
            }
            try {
                val response = YoutubeDL.getInstance().execute(request, id) { progress, eta, _ ->
                    send(mapOf("type" to "progress", "percent" to progress.toDouble(), "eta" to eta))
                }
                val path = response.out.lines().map { it.trim() }.lastOrNull { it.isNotEmpty() && File(it).exists() }
                if (path != null) {
                    MediaScannerConnection.scanFile(applicationContext, arrayOf(path), null, null)
                    send(mapOf("type" to "done", "path" to path, "name" to File(path).name))
                } else {
                    send(mapOf("type" to "error", "message" to "Dosya oluşturulamadı."))
                }
            } catch (e: YoutubeDL.CanceledException) {
                send(mapOf("type" to "cancelled"))
            } catch (e: Exception) {
                send(mapOf("type" to "error", "message" to friendlyError(e.message ?: "")))
            } finally {
                currentProcess = null
            }
        }
    }

    private fun friendlyError(raw: String): String = when {
        "Unsupported URL" in raw -> "Bu bağlantı desteklenmiyor."
        "Private video" in raw -> "Bu video gizli veya erişime kapalı."
        "Video unavailable" in raw -> "Video bulunamadı veya silinmiş."
        "Sign in to confirm" in raw -> "YouTube giriş istiyor. Uygulamayı güncelleyip (⋮ → yt-dlp'yi güncelle) tekrar dene."
        "HTTP Error 403" in raw -> "Erişim reddedildi (403). yt-dlp'yi güncelleyip tekrar dene."
        "Unable to resolve host" in raw || "Network is unreachable" in raw -> "İnternet bağlantısı yok."
        else -> raw.lines().firstOrNull { it.startsWith("ERROR") }?.removePrefix("ERROR: ")?.take(300)
            ?: "İndirme başarısız oldu."
    }

    // ---------------------------------------------------------------- helpers

    private fun send(event: Map<String, Any?>) = post { events?.success(event) }
    private fun post(block: () -> Unit) { main.post(block) }

    /** Android 9 and older need storage permission to write into Download/. */
    private fun requestLegacyStoragePermission() {
        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.P &&
            checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.WRITE_EXTERNAL_STORAGE), 1)
        }
    }

    companion object {
        private val FORMATS = setOf("best", "720p", "480p", "mp3")
    }
}

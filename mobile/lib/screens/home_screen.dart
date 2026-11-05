import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Downloads run on the phone itself (yt-dlp via youtubedl-android, see MainActivity.kt).
/// Links arrive from the website (mdhub://download?url=...) or the Android Share menu.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

enum _Phase { starting, ready, downloading, done, failed }

class _HomeScreenState extends State<HomeScreen> {
  static const _methods = MethodChannel('mdhub/downloader');
  static const _events = EventChannel('mdhub/progress');

  static const Color _accent = Color(0xFF00E5FF);
  static const Color _violet = Color(0xFF7C4DFF);
  static const Color _input = Color(0xFF0F111A);
  static const Color _border = Color(0xFF2E344E);

  final TextEditingController _urlController = TextEditingController();
  StreamSubscription<dynamic>? _sub;

  _Phase _phase = _Phase.starting;
  String _format = 'best';
  double _progress = 0;
  String _status = 'Hazırlanıyor... (ilk açılış birkaç saniye sürebilir)';
  String? _savedName;
  Map<String, String>? _pendingLink;

  static const _formats = {
    'best': 'En iyi',
    '720p': '720p',
    '480p': '480p',
    'mp3': 'MP3',
  };

  @override
  void initState() {
    super.initState();
    _sub = _events.receiveBroadcastStream().listen(_onEvent);
    _methods.setMethodCallHandler((call) async {
      if (call.method == 'onLink' && call.arguments is Map) {
        _handleLink(Map<String, String>.from(call.arguments as Map));
      }
    });
    _boot();
  }

  Future<void> _boot() async {
    try {
      final link = await _methods.invokeMethod<Map>('initialLink');
      if (link != null) _pendingLink = Map<String, String>.from(link);
      await _methods.invokeMethod('init');
      if (!mounted) return;
      setState(() {
        _phase = _Phase.ready;
        _status = 'Bağlantıyı yapıştır ya da bir uygulamadan "Paylaş" ile gönder.';
      });
      final pending = _pendingLink;
      _pendingLink = null;
      if (pending != null) _handleLink(pending);
    } on PlatformException catch (e) {
      if (!mounted) return;
      setState(() {
        _phase = _Phase.failed;
        _status = 'Başlatılamadı: ${e.message ?? e.code}';
      });
    }
  }

  void _handleLink(Map<String, String> link) {
    final url = link['url'] ?? '';
    if (url.isEmpty) return;
    if (_phase == _Phase.starting) {
      _pendingLink = link;
      return;
    }
    setState(() {
      _urlController.text = url;
      _format = _formats.containsKey(link['format']) ? link['format']! : 'best';
    });
    if (_phase != _Phase.downloading) _start();
  }

  void _onEvent(dynamic raw) {
    if (raw is! Map || !mounted) return;
    final event = Map<String, dynamic>.from(raw);
    switch (event['type']) {
      case 'progress':
        final pct = (event['percent'] as num?)?.toDouble() ?? 0;
        final eta = (event['eta'] as num?)?.toInt() ?? -1;
        setState(() {
          _progress = (pct.clamp(0, 100)) / 100.0;
          _status = eta > 0 ? 'İndiriliyor... Kalan ~${_fmtSeconds(eta)}' : 'İndiriliyor...';
        });
      case 'done':
        setState(() {
          _phase = _Phase.done;
          _progress = 1;
          _savedName = event['name'] as String?;
          _status = 'İndirilenler › Medya İndir klasörüne kaydedildi.';
        });
        _toast('İndirme tamamlandı!');
      case 'cancelled':
        setState(() {
          _phase = _Phase.ready;
          _progress = 0;
          _status = 'İndirme iptal edildi.';
        });
      case 'error':
        setState(() {
          _phase = _Phase.failed;
          _status = (event['message'] as String?) ?? 'İndirme başarısız oldu.';
        });
    }
  }

  Future<void> _start() async {
    FocusScope.of(context).unfocus();
    final url = _urlController.text.trim();
    final uri = Uri.tryParse(url);
    if (uri == null || !(uri.isScheme('http') || uri.isScheme('https')) || uri.host.isEmpty) {
      _toast('Lütfen http:// veya https:// ile başlayan bir bağlantı gir.', error: true);
      return;
    }
    setState(() {
      _phase = _Phase.downloading;
      _progress = 0;
      _savedName = null;
      _status = 'Video bilgileri alınıyor...';
    });
    try {
      await _methods.invokeMethod('download', {'url': url, 'format': _format});
    } on PlatformException catch (e) {
      setState(() {
        _phase = _Phase.failed;
        _status = e.message ?? 'İndirme başlatılamadı.';
      });
    }
  }

  Future<void> _cancel() async {
    await _methods.invokeMethod('cancel');
  }

  Future<void> _paste() async {
    final data = await Clipboard.getData('text/plain');
    final text = data?.text?.trim() ?? '';
    if (text.isNotEmpty) setState(() => _urlController.text = text);
  }

  Future<void> _updateEngine() async {
    _toast('yt-dlp güncelleniyor...');
    try {
      final status = await _methods.invokeMethod<String>('update');
      _toast(status == 'ALREADY_UP_TO_DATE' ? 'yt-dlp zaten güncel.' : 'yt-dlp güncellendi.');
    } on PlatformException catch (e) {
      _toast('Güncellenemedi: ${e.message}', error: true);
    }
  }

  String _fmtSeconds(int s) => s >= 60 ? '${s ~/ 60} dk ${s % 60} sn' : '$s sn';

  void _toast(String message, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(message),
      backgroundColor: error ? Colors.redAccent : _violet,
    ));
  }

  @override
  void dispose() {
    _sub?.cancel();
    _urlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final busy = _phase == _Phase.downloading || _phase == _Phase.starting;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Medya İndir', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
        actions: [
          PopupMenuButton<String>(
            onSelected: (v) {
              if (v == 'update') _updateEngine();
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'update', child: Text("yt-dlp'yi güncelle")),
            ],
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Text(
              'Linki yapıştır,\nvideon hazır.',
              style: TextStyle(fontSize: 32, height: 1.1, fontWeight: FontWeight.w800, letterSpacing: -1),
            ),
            const SizedBox(height: 8),
            const Text(
              'YouTube, Instagram, X ve yüzlerce siteden MP4 ya da MP3. İndirme telefonunda yapılır.',
              style: TextStyle(color: Colors.grey, fontSize: 14),
            ),
            const SizedBox(height: 20),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text('VİDEO BAĞLANTISI',
                        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Colors.grey, letterSpacing: 1)),
                    const SizedBox(height: 8),
                    Row(children: [
                      Expanded(
                        child: TextField(
                          controller: _urlController,
                          enabled: !busy,
                          keyboardType: TextInputType.url,
                          style: const TextStyle(fontSize: 14),
                          decoration: InputDecoration(
                            hintText: 'https://www.youtube.com/watch?v=...',
                            isDense: true,
                            filled: true,
                            fillColor: _input,
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(12),
                              borderSide: const BorderSide(color: _border),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton(
                        onPressed: busy ? null : _paste,
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 16),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        child: const Text('Yapıştır'),
                      ),
                    ]),
                    const SizedBox(height: 16),
                    const Text('KALİTE',
                        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Colors.grey, letterSpacing: 1)),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: _formats.entries.map((e) {
                        final selected = _format == e.key;
                        return ChoiceChip(
                          label: Text(e.value, style: const TextStyle(fontWeight: FontWeight.bold)),
                          selected: selected,
                          onSelected: busy ? null : (_) => setState(() => _format = e.key),
                          selectedColor: _accent.withValues(alpha: 0.18),
                          side: BorderSide(color: selected ? _accent : _border),
                        );
                      }).toList(),
                    ),
                    const SizedBox(height: 18),
                    SizedBox(
                      height: 52,
                      child: FilledButton.icon(
                        onPressed: busy ? null : _start,
                        icon: const Icon(Icons.download_rounded),
                        label: Text(
                          _phase == _Phase.downloading ? 'İndiriliyor...' : 'İndir',
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        style: FilledButton.styleFrom(
                          backgroundColor: _accent,
                          foregroundColor: const Color(0xFF062A31),
                          disabledBackgroundColor: _border,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Icon(
                        switch (_phase) {
                          _Phase.done => Icons.check_circle_rounded,
                          _Phase.failed => Icons.error_rounded,
                          _ => Icons.info_outline_rounded,
                        },
                        color: switch (_phase) {
                          _Phase.done => Colors.greenAccent,
                          _Phase.failed => Colors.redAccent,
                          _ => _accent,
                        },
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Expanded(child: Text(_status, style: const TextStyle(fontSize: 14))),
                    ]),
                    if (_phase == _Phase.downloading || _phase == _Phase.starting) ...[
                      const SizedBox(height: 12),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(6),
                        child: LinearProgressIndicator(
                          value: _phase == _Phase.starting || _progress == 0 ? null : _progress,
                          minHeight: 8,
                          backgroundColor: _input,
                          valueColor: const AlwaysStoppedAnimation(_accent),
                        ),
                      ),
                    ],
                    if (_phase == _Phase.downloading)
                      Align(
                        alignment: Alignment.centerRight,
                        child: TextButton(onPressed: _cancel, child: const Text('İptal et')),
                      ),
                    if (_savedName != null) ...[
                      const SizedBox(height: 8),
                      SelectableText('📁 $_savedName', style: const TextStyle(fontSize: 12, color: _accent)),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            const Text(
              'İpucu: YouTube uygulamasında Paylaş → Medya İndir ile doğrudan indirebilirsin.\n'
              'Yalnızca hakkına sahip olduğun içerikleri indir.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

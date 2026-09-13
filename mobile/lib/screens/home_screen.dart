import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final TextEditingController _urlController = TextEditingController();
  final TextEditingController _serverController = TextEditingController(
    text: 'http://10.0.2.2:8000', // Android emulator default
  );

  bool _autoSubtitle = true;
  String _selectedLang = 'tr';
  bool _autoSplit = false;
  bool _cleanAudio = false;
  String _selectedStyle = 'hormozi';
  String _selectedPosition = 'bottom';
  bool _isProcessing = false;
  
  // Status Tracking State
  String? _currentTaskId;
  double _progressPct = 0.0;
  String _stepName = 'İşlem İçin Hazır';
  String _detailText = 'URL girip "Videoyu Hazırla ve İndir" butonuna basın.';
  String? _errorMessage;
  String? _downloadedFilePath;
  Timer? _statusTimer;

  final Map<String, String> _languages = {
    'Türkçe (tr)': 'tr',
    'İngilizce (en)': 'en',
    'İspanyolca (es)': 'es',
    'Almanca (de)': 'de',
    'Fransızca (fr)': 'fr',
    'Arapça (ar)': 'ar',
    'Rusça (ru)': 'ru',
  };

  final Map<String, String> _subtitleStyles = {
    'Hormozi / Viral Pop-up': 'hormozi',
    'Minimalist Beyaz Box': 'minimalist',
    'Cyberpunk Neon': 'cyberpunk',
  };

  final Map<String, String> _subtitlePositions = {
    'Alt (Shorts/Reels)': 'bottom',
    'Orta Hizalama': 'center',
    'Üst Hizalama': 'top',
  };

  @override
  void dispose() {
    _statusTimer?.cancel();
    _urlController.dispose();
    _serverController.dispose();
    super.dispose();
  }

  Future<void> _pasteFromClipboard() async {
    final data = await Clipboard.getData('text/plain');
    if (!mounted) return;
    if (data != null && data.text != null && data.text!.isNotEmpty) {
      setState(() {
        _urlController.text = data.text!.trim();
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Panodaki bağlantı yapıştırıldı!'),
          duration: Duration(seconds: 2),
        ),
      );
    }
  }

  Future<void> _startProcess() async {
    final url = _urlController.text.trim();
    final serverUrl = _serverController.text.trim().replaceAll(RegExp(r'/$'), '');

    if (url.isEmpty) {
      _showSnackBar('Lütfen geçerli bir video URL\'si giriniz.', isError: true);
      return;
    }

    if (serverUrl.isEmpty) {
      _showSnackBar('Lütfen sunucu adresini giriniz.', isError: true);
      return;
    }

    setState(() {
      _isProcessing = true;
      _progressPct = 0.0;
      _stepName = 'Sunucuya Bağlanılıyor...';
      _detailText = 'İstek gönderiliyor...';
      _errorMessage = null;
      _downloadedFilePath = null;
    });

    try {
      final response = await http.post(
        Uri.parse('$serverUrl/api/process'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'url': url,
          'auto_subtitle': _autoSubtitle,
          'target_lang': _selectedLang,
          'auto_split': _autoSplit,
          'subtitle_style': _selectedStyle,
          'subtitle_position': _selectedPosition,
          'clean_audio': _cleanAudio,
        }),
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _currentTaskId = data['task_id'];
        _startPollingStatus(serverUrl, _currentTaskId!);
      } else {
        final err = jsonDecode(response.body);
        _handleFailure(err['detail'] ?? 'Sunucu işlemi başlatamadı.');
      }
    } catch (e) {
      _handleFailure('Sunucuya erişilemedi: $e');
    }
  }

  void _startPollingStatus(String serverUrl, String taskId) {
    _statusTimer?.cancel();
    _statusTimer = Timer.periodic(const Duration(seconds: 2), (timer) async {
      try {
        final response = await http.get(
          Uri.parse('$serverUrl/api/status/$taskId'),
        );

        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          final status = data['status'];
          final pct = (data['progress_pct'] as num).toDouble();
          final step = data['step_name'] ?? 'İşleniyor...';
          final detail = data['detail'] ?? '';

          setState(() {
            _progressPct = pct / 100.0;
            _stepName = step;
            _detailText = detail;
          });

          if (status == 'completed') {
            timer.cancel();
            _downloadFileToDevice(serverUrl, taskId);
          } else if (status == 'failed') {
            timer.cancel();
            _handleFailure(data['error'] ?? 'İşlem sırasında hata oluştu.');
          }
        }
      } catch (e) {
        // Continue polling silently on transient network blips
      }
    });
  }

  Future<void> _downloadFileToDevice(String serverUrl, String taskId) async {
    setState(() {
      _stepName = 'Dosya Telefona İndiriliyor...';
      _detailText = 'Yerel depolamaya kaydediliyor...';
    });

    try {
      final response = await http.get(
        Uri.parse('$serverUrl/api/download/$taskId'),
      );

      if (response.statusCode == 200) {
        final bytes = response.bodyBytes;
        final dir = await getApplicationDocumentsDirectory();
        final ext = _autoSplit ? 'zip' : 'mp4';
        final fileName = 'media_hub_${DateTime.now().millisecondsSinceEpoch}.$ext';
        final file = File('${dir.path}/$fileName');
        await file.writeAsBytes(bytes);

        setState(() {
          _isProcessing = false;
          _progressPct = 1.0;
          _stepName = 'İşlem Tamamlandı! 🎉';
          _detailText = 'Kaydedildi: ${file.path}';
          _downloadedFilePath = file.path;
        });

        _showSnackBar(_autoSplit ? 'Shorts klip arşivi (ZIP) indirildi!' : 'Video başarıyla indirildi!');
      } else {
        _handleFailure('Dosya indirme başarısız oldu.');
      }
    } catch (e) {
      _handleFailure('Dosya telefona kaydedilemedi: $e');
    }
  }

  void _handleFailure(String error) {
    _statusTimer?.cancel();
    setState(() {
      _isProcessing = false;
      _errorMessage = error;
      _stepName = 'Hata Oluştu ❌';
      _detailText = error;
    });
    _showSnackBar(error, isError: true);
  }

  void _showSnackBar(String message, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? Colors.redAccent : const Color(0xFF00E5FF),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: const [
            Icon(Icons.video_library_rounded, color: Color(0xFF00E5FF)),
            SizedBox(width: 8),
            Text(
              'Media Downloader Hub',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
            ),
          ],
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Server Address Settings Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: const [
                        Icon(Icons.dns_rounded, size: 18, color: Color(0xFF00E5FF)),
                        SizedBox(width: 6),
                        Text(
                          'REST API Sunucu Adresi',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _serverController,
                      style: const TextStyle(fontSize: 13),
                      decoration: InputDecoration(
                        hintText: 'http://10.0.2.2:8000 veya http://192.168.1.X:8000',
                        isDense: true,
                        filled: true,
                        fillColor: const Color(0xFF0F111A),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: const BorderSide(color: Color(0xFF2E344E)),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),

            // Main URL Input Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '🔗 Video Bağlantısı',
                      style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _urlController,
                            style: const TextStyle(fontSize: 13),
                            decoration: InputDecoration(
                              hintText: 'https://youtube.com/shorts/...',
                              isDense: true,
                              filled: true,
                              fillColor: const Color(0xFF0F111A),
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(10),
                                borderSide: const BorderSide(color: Color(0xFF2E344E)),
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        ElevatedButton.icon(
                          onPressed: _pasteFromClipboard,
                          icon: const Icon(Icons.content_paste_rounded, size: 16),
                          label: const Text('Yapıştır', style: TextStyle(fontSize: 12)),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF7C4DFF),
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),

            // Subtitle Options Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          children: const [
                            Icon(Icons.subtitles_rounded, color: Color(0xFF00E5FF), size: 20),
                            SizedBox(width: 8),
                            Text(
                              'Otomatik Altyazı & Tipografi',
                              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                            ),
                          ],
                        ),
                        Switch(
                          value: _autoSubtitle,
                          activeTrackColor: const Color(0xFF00E5FF),
                          onChanged: (val) {
                            setState(() {
                              _autoSubtitle = val;
                            });
                          },
                        ),
                      ],
                    ),
                    if (_autoSubtitle) ...[
                      const Divider(color: Color(0xFF2E344E), height: 20),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Hedef Çeviri Dili:',
                            style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                          ),
                          DropdownButton<String>(
                            value: _selectedLang,
                            dropdownColor: const Color(0xFF1A1D2B),
                            style: const TextStyle(color: Color(0xFF00E5FF), fontWeight: FontWeight.bold),
                            items: _languages.entries.map((e) {
                              return DropdownMenuItem<String>(
                                value: e.value,
                                child: Text(e.key),
                              );
                            }).toList(),
                            onChanged: (val) {
                              if (val != null) {
                                setState(() {
                                  _selectedLang = val;
                                });
                              }
                            },
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Altyazı Stili:',
                            style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                          ),
                          DropdownButton<String>(
                            value: _selectedStyle,
                            dropdownColor: const Color(0xFF1A1D2B),
                            style: const TextStyle(color: Color(0xFF00E5FF), fontWeight: FontWeight.bold),
                            items: _subtitleStyles.entries.map((e) {
                              return DropdownMenuItem<String>(
                                value: e.value,
                                child: Text(e.key),
                              );
                            }).toList(),
                            onChanged: (val) {
                              if (val != null) {
                                setState(() {
                                  _selectedStyle = val;
                                });
                              }
                            },
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Altyazı Hizalaması:',
                            style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                          ),
                          DropdownButton<String>(
                            value: _selectedPosition,
                            dropdownColor: const Color(0xFF1A1D2B),
                            style: const TextStyle(color: Color(0xFF00E5FF), fontWeight: FontWeight.bold),
                            items: _subtitlePositions.entries.map((e) {
                              return DropdownMenuItem<String>(
                                value: e.value,
                                child: Text(e.key),
                              );
                            }).toList(),
                            onChanged: (val) {
                              if (val != null) {
                                setState(() {
                                  _selectedPosition = val;
                                });
                              }
                            },
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),

            // Creator Automation Options Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: const [
                        Icon(Icons.auto_awesome_rounded, color: Color(0xFF7C4DFF), size: 20),
                        SizedBox(width: 8),
                        Text(
                          'İçerik Üretici Stüdyo Modülleri',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                        ),
                      ],
                    ),
                    const Divider(color: Color(0xFF2E344E), height: 20),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: const [
                              Text(
                                '🎬 Shorts Kliplerine Böl (30-60s)',
                                style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                              ),
                              SizedBox(height: 2),
                              Text(
                                'Whisper duraklamalarından kesip ZIP paketler',
                                style: TextStyle(fontSize: 11, color: Colors.grey),
                              ),
                            ],
                          ),
                        ),
                        Switch(
                          value: _autoSplit,
                          activeTrackColor: const Color(0xFF7C4DFF),
                          onChanged: (val) {
                            setState(() {
                              _autoSplit = val;
                            });
                          },
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: const [
                              Text(
                                '🎙️ Arka Plan Gürültüsünü Temizle (AI)',
                                style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
                              ),
                              SizedBox(height: 2),
                              Text(
                                'FFmpeg FFT gürültü filtresi & equalizer uygular',
                                style: TextStyle(fontSize: 11, color: Colors.grey),
                              ),
                            ],
                          ),
                        ),
                        Switch(
                          value: _cleanAudio,
                          activeTrackColor: const Color(0xFF7C4DFF),
                          onChanged: (val) {
                            setState(() {
                              _cleanAudio = val;
                            });
                          },
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Process Button
            SizedBox(
              height: 52,
              child: ElevatedButton.icon(
                onPressed: _isProcessing ? null : _startProcess,
                icon: _isProcessing
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.rocket_launch_rounded),
                label: Text(
                  _isProcessing ? 'İŞLENİYOR...' : '🚀 VİDEOYU HAZIRLA VE İNDİR',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF00E5FF),
                  foregroundColor: const Color(0xFF0F111A),
                  disabledBackgroundColor: const Color(0xFF2E344E),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Dynamic Progress & Status Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Text(
                            _stepName,
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 14,
                              color: _errorMessage != null
                                  ? Colors.redAccent
                                  : const Color(0xFF00E5FF),
                            ),
                          ),
                        ),
                        Text(
                          '%${(_progressPct * 100).toStringAsFixed(1)}',
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                            color: Color(0xFF7C4DFF),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(6),
                      child: LinearProgressIndicator(
                        value: _progressPct,
                        minHeight: 10,
                        backgroundColor: const Color(0xFF0F111A),
                        valueColor: AlwaysStoppedAnimation<Color>(
                          _errorMessage != null ? Colors.redAccent : const Color(0xFF00E5FF),
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      _detailText,
                      style: const TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                    if (_downloadedFilePath != null) ...[
                      const SizedBox(height: 8),
                      SelectableText(
                        '📂 Kaydedilen Konum: $_downloadedFilePath',
                        style: const TextStyle(fontSize: 11, color: Color(0xFF00E5FF)),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

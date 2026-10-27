import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import '../data/api_service.dart';
import 'analytics_service.dart';

enum VoiceCallStatus {
  connecting,
  idle,
  listening,
  processing,
  speaking,
  ended,
  error
}

class VoiceCallService extends ChangeNotifier {
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();

  VoiceCallStatus _status = VoiceCallStatus.idle;
  VoiceCallStatus get status => _status;

  String _lastUserTranscript = '';
  String get lastUserTranscript => _lastUserTranscript;

  String _lastAiReply = '';
  String get lastAiReply => _lastAiReply;

  String _statusMessage = 'Tap to speak with Juhi';
  String get statusMessage => _statusMessage;

  bool _isMuted = false;
  bool get isMuted => _isMuted;

  bool _isSpeakerOn = true;
  bool get isSpeakerOn => _isSpeakerOn;

  int _callDurationSeconds = 0;
  int get callDurationSeconds => _callDurationSeconds;

  Timer? _callDurationTimer;
  String? _currentRecordingPath;
  StreamSubscription? _playerCompleteSub;

  VoiceCallService() {
    _initPlayer();
  }

  void _initPlayer() {
    _playerCompleteSub = _player.onPlayerComplete.listen((_) {
      if (_status == VoiceCallStatus.speaking) {
        _setStatus(VoiceCallStatus.idle, 'Listening for your voice... Tap to speak');
      }
    });
  }

  void _setStatus(VoiceCallStatus newStatus, [String? message]) {
    _status = newStatus;
    if (message != null) {
      _statusMessage = message;
    }
    notifyListeners();
  }

  /// Start a voice call session with Juhi
  Future<bool> startCall(String userId, {String? partnerName}) async {
    _callDurationSeconds = 0;
    _lastUserTranscript = '';
    _lastAiReply = '';
    _setStatus(VoiceCallStatus.connecting, 'Calling ${partnerName ?? "Juhi"}... 💕');

    final micGranted = await requestMicPermission();
    if (!micGranted) {
      _setStatus(VoiceCallStatus.error, 'Microphone permission is required for voice calls.');
      return false;
    }

    _callDurationTimer?.cancel();
    _callDurationTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      _callDurationSeconds++;
      notifyListeners();
    });

    analyticsService.logEvent('voice_call_started', category: 'voice_call', immediate: true);

    // Initial greeting synthesis
    try {
      const greetReply = "Hey! I'm so glad you called me. How has your day been, sweetie?";
      _lastAiReply = greetReply;
      _setStatus(VoiceCallStatus.processing, '${partnerName ?? "Juhi"} is answering...');

      final ttsResult = await apiService.synthesizeSpeech(text: greetReply);
      final audioB64 = ttsResult['audio_base64'] as String?;
      if (audioB64 != null && audioB64.isNotEmpty) {
        await _playBase64Audio(audioB64);
        _setStatus(VoiceCallStatus.speaking, '${partnerName ?? "Juhi"} is speaking... 💕');
      } else {
        _setStatus(VoiceCallStatus.idle, 'Connected! Tap microphone to speak');
      }
    } catch (e) {
      debugPrint('[VoiceCallService] Greeting error: $e');
      _setStatus(VoiceCallStatus.idle, 'Connected! Tap microphone to speak');
    }

    return true;
  }

  /// Request microphone permission
  Future<bool> requestMicPermission() async {
    return await _recorder.hasPermission();
  }

  DateTime? _recordingStartTime;
  bool get isRecording => _status == VoiceCallStatus.listening;

  /// Start recording user's speech in 16kHz mono WAV format (ideal for Sarvam Saaras v4)
  Future<void> startRecording() async {
    if (_status == VoiceCallStatus.speaking) {
      await _player.stop();
    }

    final hasPerm = await _recorder.hasPermission();
    if (!hasPerm) {
      _setStatus(VoiceCallStatus.error, 'Microphone permission needed to talk with Juhi');
      return;
    }

    try {
      final dir = await getTemporaryDirectory();
      final path = '${dir.path}/voice_${DateTime.now().millisecondsSinceEpoch}.wav';
      _currentRecordingPath = path;
      _recordingStartTime = DateTime.now();

      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.wav,
          sampleRate: 16000,
          numChannels: 1,
        ),
        path: path,
      );

      _setStatus(VoiceCallStatus.listening, 'Juhi is listening... Speak now 🎙️');
    } catch (e) {
      debugPrint('[VoiceCallService] Start recording error: $e');
      _setStatus(VoiceCallStatus.error, 'Could not start recording: $e');
    }
  }

  /// Stop recording and process call turn via Sarvam Saaras v4 STT & Bulbul v4 TTS
  Future<void> stopRecordingAndSend(String userId) async {
    if (_status != VoiceCallStatus.listening) return;

    // Buffer protection: if the recording was ultra-short, wait briefly to capture full syllable
    if (_recordingStartTime != null) {
      final elapsed = DateTime.now().difference(_recordingStartTime!).inMilliseconds;
      if (elapsed < 600) {
        await Future.delayed(Duration(milliseconds: 600 - elapsed));
      }
    }

    try {
      final path = await _recorder.stop();
      final recordedPath = path ?? _currentRecordingPath;

      if (recordedPath == null || !File(recordedPath).existsSync()) {
        _setStatus(VoiceCallStatus.idle, 'Tap microphone to speak with Juhi');
        return;
      }

      final file = File(recordedPath);
      final fileSize = await file.length();
      debugPrint('[VoiceCallService] Recorded WAV size: $fileSize bytes');

      // Ignore micro-recordings under 2500 bytes (header only)
      if (fileSize < 2500) {
        _setStatus(VoiceCallStatus.idle, 'Tap and speak for a moment so Juhi can hear you!');
        try { file.deleteSync(); } catch (_) {}
        return;
      }

      _setStatus(VoiceCallStatus.processing, 'Juhi is listening & thinking... ✨');

      final result = await apiService.sendVoiceCallTurn(
        userId: userId,
        filePath: recordedPath,
      );

      final userTranscript = (result['user_transcript'] as String?) ?? '';
      final aiReply = (result['ai_reply'] as String?) ?? '';
      final audioBase64 = result['audio_base64'] as String?;
      final isPaywall = result['is_paywall'] == true;

      _lastUserTranscript = userTranscript;
      _lastAiReply = aiReply;

      if (isPaywall) {
        analyticsService.logEvent('voice_call_paywall_hit', category: 'monetization', immediate: true);
      }

      if (audioBase64 != null && audioBase64.isNotEmpty) {
        _setStatus(VoiceCallStatus.speaking, 'Juhi is speaking... 💕');
        await _playBase64Audio(audioBase64);
      } else {
        _setStatus(VoiceCallStatus.idle, 'Tap microphone to speak');
      }

      // Cleanup local temp file
      try {
        file.deleteSync();
      } catch (_) {}
    } catch (e) {
      debugPrint('[VoiceCallService] Turn processing error: $e');
      _setStatus(VoiceCallStatus.idle, 'Connection hiccup. Tap to speak again.');
    }
  }

  /// Toggle recording state (single tap to talk, single tap to finish)
  Future<void> toggleRecording(String userId) async {
    if (_status == VoiceCallStatus.listening) {
      await stopRecordingAndSend(userId);
    } else {
      await startRecording();
    }
  }

  /// Play base64 WAV audio bytes
  Future<void> _playBase64Audio(String base64Str) async {
    try {
      final bytes = base64Decode(base64Str);
      final dir = await getTemporaryDirectory();
      final tempAudioFile = File('${dir.path}/juhi_voice_${DateTime.now().millisecondsSinceEpoch}.wav');
      await tempAudioFile.writeAsBytes(bytes);

      await _player.stop();
      await _player.play(DeviceFileSource(tempAudioFile.path));
    } catch (e) {
      debugPrint('[VoiceCallService] Play audio error: $e');
      _setStatus(VoiceCallStatus.idle, 'Tap microphone to speak');
    }
  }

  /// Play speech for any text message in chat
  Future<void> speakChatMessage(String text, {String? speaker}) async {
    try {
      final result = await apiService.synthesizeSpeech(text: text, speaker: speaker);
      final audioB64 = result['audio_base64'] as String?;
      if (audioB64 != null && audioB64.isNotEmpty) {
        await _playBase64Audio(audioB64);
      }
    } catch (e) {
      debugPrint('[VoiceCallService] Speak message error: $e');
    }
  }

  /// Stop currently playing speech
  Future<void> stopSpeaking() async {
    await _player.stop();
    if (_status == VoiceCallStatus.speaking) {
      _setStatus(VoiceCallStatus.idle, 'Tap microphone to speak');
    }
  }

  /// Toggle microphone mute
  void toggleMute() {
    _isMuted = !_isMuted;
    notifyListeners();
  }

  /// Toggle speakerphone
  void toggleSpeaker() {
    _isSpeakerOn = !_isSpeakerOn;
    notifyListeners();
  }

  /// End voice call
  Future<void> endCall() async {
    _callDurationTimer?.cancel();
    _callDurationTimer = null;

    try {
      if (await _recorder.isRecording()) {
        await _recorder.stop();
      }
    } catch (_) {}

    try {
      await _player.stop();
    } catch (_) {}

    analyticsService.logEvent(
      'voice_call_ended',
      category: 'voice_call',
      metadata: {'duration_seconds': _callDurationSeconds},
      immediate: true,
    );

    _setStatus(VoiceCallStatus.ended, 'Call ended');
  }

  @override
  void dispose() {
    _callDurationTimer?.cancel();
    _playerCompleteSub?.cancel();
    _recorder.dispose();
    _player.dispose();
    super.dispose();
  }
}

// Global voice call service instance
final voiceCallService = VoiceCallService();

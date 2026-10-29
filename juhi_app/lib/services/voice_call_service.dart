import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:audioplayers/audioplayers.dart';
import 'package:dio/dio.dart';
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

/// Full-Duplex Continuous Phone Call Service
///
/// Operates just like a real phone call:
/// 1. Connects and greets the user.
/// 2. As soon as Juhi finishes speaking, microphone automatically listens hands-free.
/// 3. Detects user speech and silence automatically (Voice Activity Detection).
/// 4. Sends turn, plays Juhi's voice response, and immediately listens again.
/// 5. Runs continuously back-and-forth until the call is hung up.
class VoiceCallService extends ChangeNotifier {
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();

  VoiceCallStatus _status = VoiceCallStatus.idle;
  VoiceCallStatus get status => _status;

  String _lastUserTranscript = '';
  String get lastUserTranscript => _lastUserTranscript;

  String _lastAiReply = '';
  String get lastAiReply => _lastAiReply;

  String _statusMessage = 'Connecting...';
  String get statusMessage => _statusMessage;

  bool _isMuted = false;
  bool get isMuted => _isMuted;

  bool _isSpeakerOn = true;
  bool get isSpeakerOn => _isSpeakerOn;

  int _callDurationSeconds = 0;
  int get callDurationSeconds => _callDurationSeconds;

  int _remainingVoiceSeconds = 120;
  int get remainingVoiceSeconds => _remainingVoiceSeconds;

  bool _isCallActive = false;
  bool get isCallActive => _isCallActive;

  String? _currentUserId;
  String _partnerName = 'Juhi';
  String get partnerName => _partnerName;

  bool _hasUserSpoken = false;
  bool get hasUserSpoken => _hasUserSpoken;

  double _normalizedAmplitude = 0.0;
  double get normalizedAmplitude => _normalizedAmplitude;

  void Function()? onPaywallTriggered;

  Timer? _callDurationTimer;
  String? _currentRecordingPath;
  StreamSubscription? _playerCompleteSub;
  StreamSubscription<Amplitude>? _amplitudeSub;
  DateTime? _recordingStartTime;
  DateTime? _lastSpeechTime;
  int _speechFramesCount = 0;
  bool _isProcessingTurn = false;

  // Thresholds for Voice Activity Detection (VAD)
  static const double _speechThresholdDb = -40.0;
  static const int _silencePauseTimeoutMs = 1300;
  static const int _maxTurnSeconds = 25;
  static const int _idleBufferRecycleSeconds = 12;

  VoiceCallService() {
    _initPlayer();
  }

  void _initPlayer() {
    _playerCompleteSub = _player.onPlayerComplete.listen((_) {
      debugPrint('[VoiceCallService] Playback finished. Status: $_status, CallActive: $_isCallActive');
      if (_status == VoiceCallStatus.speaking && _isCallActive) {
        if (!_isMuted) {
          _startAutoListening();
        } else {
          _setStatus(VoiceCallStatus.idle, 'Microphone muted 🔇');
        }
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

  void setRemainingVoiceSeconds(int seconds) {
    _remainingVoiceSeconds = seconds;
    notifyListeners();
  }

  Future<void> refreshBalance(String userId) async {
    try {
      final bal = await apiService.getVoiceBalance(userId);
      _remainingVoiceSeconds = bal;
      notifyListeners();
    } catch (_) {}
  }

  /// Start a voice call session with Juhi in full hands-free phone mode
  Future<bool> startCall(String userId, {String? partnerName, bool isSubscribed = false}) async {
    _isCallActive = true;
    _currentUserId = userId;
    _partnerName = partnerName ?? 'Juhi';
    _callDurationSeconds = 0;
    _lastUserTranscript = '';
    _lastAiReply = '';
    _hasUserSpoken = false;
    _normalizedAmplitude = 0.0;
    _isProcessingTurn = false;

    _setStatus(VoiceCallStatus.connecting, 'Calling $_partnerName... 💕');

    final micGranted = await requestMicPermission();
    if (!micGranted) {
      _isCallActive = false;
      _setStatus(VoiceCallStatus.error, 'Microphone permission is required for voice calls.');
      return false;
    }

    // Fetch current voice call balance
    try {
      final bal = await apiService.getVoiceBalance(userId);
      _remainingVoiceSeconds = bal > 0 ? bal : (isSubscribed ? 900 : 0);
    } catch (_) {
      if (isSubscribed) _remainingVoiceSeconds = 900;
    }

    _callDurationTimer?.cancel();
    _callDurationTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!_isCallActive) {
        timer.cancel();
        return;
      }
      _callDurationSeconds++;
      if (_remainingVoiceSeconds > 0) {
        _remainingVoiceSeconds--;
        if (_remainingVoiceSeconds == 0 && !isSubscribed) {
          onPaywallTriggered?.call();
        }
      }
      notifyListeners();
    });

    analyticsService.logEvent('voice_call_started', category: 'voice_call', immediate: true);

    // Initial greeting synthesis (Juhi answers the call)
    try {
      const greetReply = "Hey! I'm so glad you called me. How has your day been, sweetie?";
      _lastAiReply = greetReply;
      _setStatus(VoiceCallStatus.processing, '$_partnerName is answering...');

      final ttsResult = await apiService.synthesizeSpeech(text: greetReply);
      final audioB64 = ttsResult['audio_base64'] as String?;

      if (!_isCallActive) return false;

      if (audioB64 != null && audioB64.isNotEmpty) {
        _setStatus(VoiceCallStatus.speaking, '$_partnerName is speaking... 💕');
        await _playBase64Audio(audioB64);
        // Note: When audio finishes, _player.onPlayerComplete automatically calls _startAutoListening()
      } else {
        // Fallback: start listening immediately
        _startAutoListening();
      }
    } catch (e) {
      debugPrint('[VoiceCallService] Greeting error: $e');
      if (_isCallActive) {
        _startAutoListening();
      }
    }

    return true;
  }

  /// Request microphone permission
  Future<bool> requestMicPermission() async {
    return await _recorder.hasPermission();
  }

  bool get isRecording => _status == VoiceCallStatus.listening;

  /// Internal recorder starter
  Future<void> _startRecordingInternal() async {
    try {
      if (await _recorder.isRecording()) {
        await _recorder.stop();
      }
    } catch (_) {}

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
  }

  /// Automatically activates microphone and listens with Voice Activity Detection (VAD)
  Future<void> _startAutoListening() async {
    if (!_isCallActive || _isMuted) return;
    if (_status == VoiceCallStatus.processing || _status == VoiceCallStatus.speaking) return;

    try {
      _amplitudeSub?.cancel();
      _amplitudeSub = null;
      _hasUserSpoken = false;
      _speechFramesCount = 0;
      _lastSpeechTime = null;
      _normalizedAmplitude = 0.0;
      _isProcessingTurn = false;

      await _startRecordingInternal();

      _setStatus(VoiceCallStatus.listening, 'Juhi is listening... Speak anytime 🎙️');

      // Monitor live microphone amplitude for speech detection & silence timeout
      _amplitudeSub = _recorder.onAmplitudeChanged(const Duration(milliseconds: 120)).listen(
        _onAmplitudeTick,
        onError: (err) {
          debugPrint('[VoiceCallService] Amplitude stream error: $err');
        },
      );
    } catch (e) {
      debugPrint('[VoiceCallService] Start auto-listening error: $e');
      if (_isCallActive && !_isMuted) {
        _setStatus(VoiceCallStatus.idle, 'Tap to retry connection');
      }
    }
  }

  /// Voice Activity Detection & Silence Timeout handler
  void _onAmplitudeTick(Amplitude amp) {
    if (!_isCallActive || _status != VoiceCallStatus.listening || _isProcessingTurn) return;

    final currentDb = amp.current.isFinite ? amp.current : -100.0;

    // Normalize amplitude to 0.0 - 1.0 range (from -50 dB up to -15 dB)
    final rawNorm = ((currentDb + 50.0) / 35.0).clamp(0.0, 1.0);
    _normalizedAmplitude = (_normalizedAmplitude * 0.3) + (rawNorm * 0.7);

    // Voice Activity Detection: Check if current audio exceeds speech threshold
    if (currentDb > _speechThresholdDb) {
      _speechFramesCount++;
      // Require at least 2 consecutive speech frames (~240ms) to filter clicks/tapping
      if (_speechFramesCount >= 2) {
        if (!_hasUserSpoken) {
          _hasUserSpoken = true;
          _setStatus(VoiceCallStatus.listening, 'Listening to you... 🗣️');
        }
        _lastSpeechTime = DateTime.now();
      }
      notifyListeners();
      return;
    }

    // Silence detection after user has spoken
    if (_hasUserSpoken && _lastSpeechTime != null) {
      final silenceMs = DateTime.now().difference(_lastSpeechTime!).inMilliseconds;
      final totalTurnSec = _recordingStartTime != null
          ? DateTime.now().difference(_recordingStartTime!).inSeconds
          : 0;

      // User finished sentence (pause >= 1.3s) or reached max turn duration (25s)
      if (silenceMs >= _silencePauseTimeoutMs || totalTurnSec >= _maxTurnSeconds) {
        debugPrint('[VoiceCallService] Silence detected (${silenceMs}ms). Triggering auto send turn.');
        _triggerAutoTurn();
        return;
      }
    }

    // Idle buffer recycling: if user hasn't spoken for 12 seconds, quietly recycle the file
    if (!_hasUserSpoken && _recordingStartTime != null) {
      final idleSec = DateTime.now().difference(_recordingStartTime!).inSeconds;
      if (idleSec >= _idleBufferRecycleSeconds) {
        _recycleRecordingBuffer();
        return;
      }
    }

    notifyListeners();
  }

  /// Silently reset the recording file if the user hasn't spoken to keep WAV size minimal
  Future<void> _recycleRecordingBuffer() async {
    if (!_isCallActive || _isMuted || _hasUserSpoken || _status != VoiceCallStatus.listening) {
      return;
    }
    try {
      _amplitudeSub?.cancel();
      _amplitudeSub = null;
      final path = await _recorder.stop();
      if (path != null) {
        try {
          File(path).deleteSync();
        } catch (_) {}
      }
      if (_isCallActive && !_isMuted && !_hasUserSpoken && _status == VoiceCallStatus.listening) {
        await _startRecordingInternal();
        _amplitudeSub = _recorder.onAmplitudeChanged(const Duration(milliseconds: 120)).listen(_onAmplitudeTick);
      }
    } catch (e) {
      debugPrint('[VoiceCallService] Recycle buffer error: $e');
    }
  }

  /// Trigger automatic turn submission when speech completes
  void _triggerAutoTurn() {
    if (_isProcessingTurn || !_isCallActive) return;
    _isProcessingTurn = true;
    _amplitudeSub?.cancel();
    _amplitudeSub = null;
    _normalizedAmplitude = 0.0;

    stopRecordingAndSend(_currentUserId ?? '7770001');
  }

  /// Start listening manually if idle
  Future<void> manualStartListening() async {
    if (!_isCallActive) return;
    if (_status == VoiceCallStatus.idle || _status == VoiceCallStatus.error) {
      _isMuted = false;
      await _startAutoListening();
    }
  }

  /// Manually force-send current speech (e.g. if user taps while speaking)
  Future<void> manualSendTurn(String userId) async {
    _hasUserSpoken = true;
    _isProcessingTurn = true;
    _amplitudeSub?.cancel();
    _amplitudeSub = null;
    _normalizedAmplitude = 0.0;
    await stopRecordingAndSend(userId);
  }

  /// Stop recording and process turn via Sarvam Saaras v4 STT & Bulbul v4 TTS
  Future<void> stopRecordingAndSend(String userId) async {
    _amplitudeSub?.cancel();
    _amplitudeSub = null;
    _normalizedAmplitude = 0.0;

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

      if (!_isCallActive) {
        if (recordedPath != null) {
          try { File(recordedPath).deleteSync(); } catch (_) {}
        }
        return;
      }

      if (recordedPath == null || !File(recordedPath).existsSync()) {
        if (_isCallActive && !_isMuted) {
          _startAutoListening();
        }
        return;
      }

      final file = File(recordedPath);
      final fileSize = await file.length();
      debugPrint('[VoiceCallService] Recorded WAV size: $fileSize bytes, UserSpoke: $_hasUserSpoken');

      // Ignore silent recordings or accidental tiny bursts (less than 1200 bytes)
      if ((!_hasUserSpoken && fileSize < 3200) || fileSize < 1200) {
        try { file.deleteSync(); } catch (_) {}
        if (_isCallActive && !_isMuted) {
          await Future.delayed(const Duration(milliseconds: 150));
          _startAutoListening();
        }
        return;
      }

      _setStatus(VoiceCallStatus.processing, '$_partnerName is thinking... ✨');

      final result = await apiService.sendVoiceCallTurn(
        userId: userId,
        filePath: recordedPath,
      );

      if (!_isCallActive) {
        try { file.deleteSync(); } catch (_) {}
        return;
      }

      final userTranscript = (result['user_transcript'] as String?) ?? '';
      final aiReply = (result['ai_reply'] as String?) ?? '';
      final audioBase64 = result['audio_base64'] as String?;
      final isPaywall = result['is_paywall'] == true;

      _lastUserTranscript = userTranscript;
      _lastAiReply = aiReply;

      if (result['remaining_voice_seconds'] != null) {
        _remainingVoiceSeconds = (result['remaining_voice_seconds'] as num).toInt();
        notifyListeners();
      }

      if (isPaywall) {
        analyticsService.logEvent('voice_call_paywall_hit', category: 'monetization', immediate: true);
        onPaywallTriggered?.call();
        try { file.deleteSync(); } catch (_) {}
        return;
      }

      if (audioBase64 != null && audioBase64.isNotEmpty) {
        _setStatus(VoiceCallStatus.speaking, '$_partnerName is speaking... 💕');
        await _playBase64Audio(audioBase64);
        // Note: When audio finishes playing, _player.onPlayerComplete resumes auto-listening!
      } else {
        // If no audio returned, automatically continue listening
        if (_isCallActive && !_isMuted) {
          await Future.delayed(const Duration(milliseconds: 300));
          _startAutoListening();
        }
      }

      // Cleanup local temp file
      try {
        file.deleteSync();
      } catch (_) {}
    } catch (e, st) {
      debugPrint('[VoiceCallService] Turn processing error: $e\n$st');
      if (!_isCallActive) return;

      String msg = 'Reconnecting with $_partnerName...';
      if (e is DioException) {
        if (e.type == DioExceptionType.connectionTimeout || e.type == DioExceptionType.receiveTimeout) {
          msg = 'Connection hiccup. Reconnecting...';
        } else if (e.response?.data is Map && (e.response!.data as Map)['error'] != null) {
          msg = (e.response!.data as Map)['error'].toString();
        }
      }
      _setStatus(VoiceCallStatus.idle, msg);

      // Auto-recover after momentary error
      if (_isCallActive && !_isMuted) {
        await Future.delayed(const Duration(milliseconds: 1400));
        if (_isCallActive && !_isMuted) {
          _startAutoListening();
        }
      }
    } finally {
      _isProcessingTurn = false;
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
      if (_isCallActive && !_isMuted) {
        await Future.delayed(const Duration(milliseconds: 400));
        _startAutoListening();
      }
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

  /// Stop currently playing speech (conversational interruption / barge-in)
  Future<void> stopSpeaking() async {
    await _player.stop();
    if (_isCallActive && !_isMuted) {
      await _startAutoListening();
    } else {
      _setStatus(VoiceCallStatus.idle, 'Ready');
    }
  }

  /// Toggle microphone mute
  void toggleMute() {
    _isMuted = !_isMuted;
    if (_isMuted) {
      _amplitudeSub?.cancel();
      _amplitudeSub = null;
      _recorder.stop().then((path) {
        if (path != null) {
          try { File(path).deleteSync(); } catch (_) {}
        }
      }).catchError((_) {});
      _setStatus(VoiceCallStatus.idle, 'Microphone muted 🔇');
    } else {
      if (_isCallActive && _status != VoiceCallStatus.speaking && _status != VoiceCallStatus.processing) {
        _startAutoListening();
      }
    }
    notifyListeners();
  }

  /// Toggle speakerphone
  void toggleSpeaker() {
    _isSpeakerOn = !_isSpeakerOn;
    notifyListeners();
  }

  /// End voice call session completely
  Future<void> endCall() async {
    _isCallActive = false;
    _callDurationTimer?.cancel();
    _callDurationTimer = null;
    _amplitudeSub?.cancel();
    _amplitudeSub = null;
    _normalizedAmplitude = 0.0;
    _isProcessingTurn = false;

    try {
      if (await _recorder.isRecording()) {
        final path = await _recorder.stop();
        if (path != null) {
          try { File(path).deleteSync(); } catch (_) {}
        }
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
    _isCallActive = false;
    _callDurationTimer?.cancel();
    _amplitudeSub?.cancel();
    _playerCompleteSub?.cancel();
    _recorder.dispose();
    _player.dispose();
    super.dispose();
  }
}

// Global voice call service instance
final voiceCallService = VoiceCallService();

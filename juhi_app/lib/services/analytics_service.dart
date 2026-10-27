import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';
import '../data/api_service.dart';
import '../data/local_storage.dart';

/// Robust client-side telemetry service that tracks every user action,
/// screen navigation, intimacy/mode change, chat event, and payment funnel.
class AnalyticsService {
  static final AnalyticsService _instance = AnalyticsService._internal();
  factory AnalyticsService() => _instance;
  AnalyticsService._internal();

  final List<Map<String, dynamic>> _eventQueue = [];
  Timer? _flushTimer;
  bool _isFlushing = false;

  late final String _sessionId;
  DateTime _sessionStartTime = DateTime.now();
  String? _currentScreen;

  String get sessionId => _sessionId;

  /// Initializes the analytics service session and periodic batch flusher
  void init() {
    _sessionId = const Uuid().v4();
    _sessionStartTime = DateTime.now();

    // Periodic flusher every 5 seconds
    _flushTimer?.cancel();
    _flushTimer = Timer.periodic(const Duration(seconds: 5), (_) => flush());

    logAppOpen();
  }

  void dispose() {
    _flushTimer?.cancel();
    flush();
  }

  // ── Core Event Logger ───────────────────────────────────────────────────────
  Future<void> logEvent(
    String eventName, {
    String category = 'engagement',
    Map<String, dynamic>? metadata,
    bool immediate = false,
  }) async {
    try {
      final userId = await LocalStorage.getUserId() ?? '0';

      final eventPayload = {
        'user_id': userId,
        'event_name': eventName,
        'event_category': category,
        'platform': 'android_app',
        'created_at': DateTime.now().toUtc().toIso8601String(),
        'metadata': {
          'session_id': _sessionId,
          'screen': _currentScreen,
          ...?metadata,
        },
      };

      _eventQueue.add(eventPayload);

      if (kDebugMode) {
        // ignore: avoid_print
        print('[TELEMETRY] $category:$eventName -> ${eventPayload['metadata']}');
      }

      if (immediate || _eventQueue.length >= 10) {
        await flush();
      }
    } catch (e) {
      if (kDebugMode) {
        // ignore: avoid_print
        print('[AnalyticsService Error] $e');
      }
    }
  }

  /// Flushes buffered events to the backend in a single batch
  Future<void> flush() async {
    if (_isFlushing || _eventQueue.isEmpty) return;
    _isFlushing = true;

    final batchToSend = List<Map<String, dynamic>>.from(_eventQueue);
    _eventQueue.clear();

    try {
      final success = await apiService.sendAnalyticsBatch(batchToSend);
      if (!success) {
        // Re-queue on failure so telemetry is never lost on network blips
        _eventQueue.insertAll(0, batchToSend);
      }
    } catch (_) {
      _eventQueue.insertAll(0, batchToSend);
    } finally {
      _isFlushing = false;
    }
  }

  // ── High-Level Event Tracking Helpers ──────────────────────────────────────

  /// Screen Navigation View
  void logScreenView(String screenName, {String? fromScreen}) {
    if (_currentScreen == screenName) return;
    final prev = _currentScreen;
    _currentScreen = screenName;

    logEvent(
      'screen_view',
      category: 'navigation',
      metadata: {
        'screen_name': screenName,
        'previous_screen': fromScreen ?? prev,
      },
      immediate: true,
    );
  }

  /// Bottom Navigation Tab Switch
  void logTabSwitch(String fromTab, String toTab, int tabIndex) {
    logEvent(
      'tab_switched',
      category: 'navigation',
      metadata: {
        'from_tab': fromTab,
        'to_tab': toTab,
        'tab_index': tabIndex,
      },
    );
  }

  /// App Lifecycle
  void logAppOpen() {
    _sessionStartTime = DateTime.now();
    logEvent(
      'app_open',
      category: 'lifecycle',
      metadata: {
        'session_id': _sessionId,
      },
      immediate: true,
    );
  }

  void logAppResume() {
    logEvent(
      'app_resumed',
      category: 'lifecycle',
      metadata: {
        'session_id': _sessionId,
      },
    );
  }

  void logAppPause() {
    final durationSec = DateTime.now().difference(_sessionStartTime).inSeconds;
    logEvent(
      'session_end',
      category: 'lifecycle',
      metadata: {
        'session_id': _sessionId,
        'duration_seconds': durationSec,
      },
      immediate: true,
    );
    flush();
  }

  // ── Onboarding ─────────────────────────────────────────────────────────────
  void logOnboardingStep(int stepIndex, String title) {
    logEvent(
      'onboarding_step_viewed',
      category: 'onboarding',
      metadata: {
        'step_index': stepIndex,
        'step_title': title,
      },
    );
  }

  void logOnboardingComplete(String userName) {
    logEvent(
      'onboarding_completed',
      category: 'onboarding',
      metadata: {
        'user_nickname': userName,
      },
      immediate: true,
    );
  }

  // ── Chat & Intimacy Events ─────────────────────────────────────────────────
  void logMessageSent({required int length, required int words, String? promptType}) {
    logEvent(
      'message_sent',
      category: 'chat',
      metadata: {
        'text_length': length,
        'word_count': words,
        'prompt_type': promptType ?? 'custom_text',
      },
      immediate: true,
    );
  }

  void logAiReplyReceived({
    required int length,
    bool hasImage = false,
    bool hasGif = false,
    int? remainingFree,
  }) {
    logEvent(
      'ai_reply_received',
      category: 'chat',
      metadata: {
        'reply_length': length,
        'has_image': hasImage,
        'has_gif': hasGif,
        'remaining_free': remainingFree,
      },
    );
  }

  void logQuickPromptClicked(String promptText) {
    logEvent(
      'quick_prompt_clicked',
      category: 'chat',
      metadata: {'prompt': promptText},
    );
  }

  void logModeToggled(String newMode) {
    logEvent(
      'mode_toggled',
      category: 'companion',
      metadata: {
        'new_mode': newMode,
        'is_intimate': newMode == 'intimate' || newMode == 'girlfriend',
      },
      immediate: true,
    );
  }

  void logRelationshipStageSelected(int level, String title) {
    logEvent(
      'relationship_level_selected',
      category: 'companion',
      metadata: {
        'level': level,
        'title': title,
      },
      immediate: true,
    );
  }

  void logChatCleared() {
    logEvent(
      'chat_cleared',
      category: 'chat',
      immediate: true,
    );
  }

  // ── Monetization & Store Funnel ────────────────────────────────────────────
  void logStoreViewed() {
    logEvent(
      'store_screen_viewed',
      category: 'monetization',
      immediate: true,
    );
  }

  void logPaywallShown({required int freeUsed, int limit = 50}) {
    logEvent(
      'paywall_modal_shown',
      category: 'monetization',
      metadata: {
        'free_messages_used': freeUsed,
        'limit': limit,
      },
      immediate: true,
    );
  }

  void logPlanSelected({
    required String planType,
    required String planTitle,
    required int amountInr,
  }) {
    logEvent(
      'plan_selected',
      category: 'monetization',
      metadata: {
        'plan_type': planType,
        'plan_title': planTitle,
        'amount': amountInr,
      },
      immediate: true,
    );
  }

  void logCheckoutInitiated({
    required String orderId,
    required String planType,
    required int amountPaise,
    required String gateway,
  }) {
    logEvent(
      'checkout_initiated',
      category: 'monetization',
      metadata: {
        'order_id': orderId,
        'plan_type': planType,
        'amount': amountPaise / 100,
        'gateway': gateway,
      },
      immediate: true,
    );
  }

  void logPaymentSuccess({
    required String orderId,
    required String paymentId,
    required String planType,
  }) {
    logEvent(
      'payment_success',
      category: 'monetization',
      metadata: {
        'order_id': orderId,
        'payment_id': paymentId,
        'plan_type': planType,
      },
      immediate: true,
    );
  }

  void logPaymentFailed({
    required String? orderId,
    required String reason,
  }) {
    logEvent(
      'payment_failed',
      category: 'monetization',
      metadata: {
        'order_id': orderId,
        'failure_reason': reason,
      },
      immediate: true,
    );
  }

  // ── Memories & Settings ────────────────────────────────────────────────────
  void logMemoryCardClicked(String category, String memoryText) {
    logEvent(
      'memory_card_clicked',
      category: 'companion',
      metadata: {
        'memory_category': category,
        'snippet': memoryText.length > 50 ? '${memoryText.substring(0, 50)}...' : memoryText,
      },
    );
  }

  void logMemoriesCleared() {
    logEvent('memories_cleared', category: 'companion', immediate: true);
  }

  void logSettingToggled(String settingKey, bool enabled) {
    logEvent(
      'setting_toggled',
      category: 'settings',
      metadata: {
        'setting': settingKey,
        'enabled': enabled,
      },
    );
  }
}

// Singleton global access
final analyticsService = AnalyticsService();

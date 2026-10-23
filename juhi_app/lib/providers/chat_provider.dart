import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/api_service.dart';
import '../data/local_storage.dart';
import '../models/chat_message.dart';
import '../services/notification_service.dart';

// ── Chat Provider ──────────────────────────────────────────────────────────────
final chatProvider =
    AsyncNotifierProvider<ChatNotifier, List<ChatMessage>>(ChatNotifier.new);

class ChatNotifier extends AsyncNotifier<List<ChatMessage>> {
  @override
  Future<List<ChatMessage>> build() async {
    return await _loadHistory();
  }

  Future<List<ChatMessage>> _loadHistory() async {
    final userId = await LocalStorage.getUserId();
    if (userId == null) return [];

    try {
      final data = await apiService.getChatHistory(userId);
      if (data['success'] == true) {
        final history = (data['history'] as List)
            .map((m) => ChatMessage.fromJson(m as Map<String, dynamic>))
            .toList();

        return history;
      }
    } catch (e) {
      // ignore: avoid_print
      print('[ChatProvider] Error loading history: $e');
    }
    return [];
  }

  /// Checks whether Juhi has a proactive message or check-in to initiate
  Future<bool> checkProactiveMessage({
    bool force = false,
    bool showNotification = false,
  }) async {
    final userId = await LocalStorage.getUserId();
    if (userId == null) return false;

    try {
      final proRes = await apiService.checkProactive(userId, force: force);
      if (proRes['success'] == true &&
          proRes['has_proactive'] == true &&
          proRes['message'] != null) {
        final msgText = proRes['message'].toString();
        final current = state.valueOrNull ?? [];

        // Avoid adding duplicate if already present as last message
        if (current.isNotEmpty && current.last.content == msgText) {
          return false;
        }

        final proactiveMsg = ChatMessage(
          role: 'assistant',
          content: msgText,
          timestamp: DateTime.now(),
        );
        state = AsyncData([...current, proactiveMsg]);

        if (showNotification) {
          final isProactiveEnabled = await LocalStorage.isProactiveEnabled();
          final isNotifsEnabled = await LocalStorage.isNotificationsEnabled();
          final isSoundEnabled = await LocalStorage.isSoundEnabled();
          if (isProactiveEnabled && isNotifsEnabled) {
            final title = (proRes['title'] ?? 'Juhi 💕').toString();
            await notificationService.showJuhiNotification(
              id: 8888,
              title: title,
              body: msgText,
              playSound: isSoundEnabled,
              payload: '/chat',
            );
          }
        }
        return true;
      }
    } catch (e) {
      // ignore: avoid_print
      print('[ChatProvider] Check proactive error: $e');
    }
    return false;
  }

  /// Sends a message and returns the backend response map (with level-up/paywall flags)
  Future<Map<String, dynamic>?> sendMessage(String text) async {
    final userId = await LocalStorage.getUserId();
    if (userId == null) return null;

    final current = state.valueOrNull ?? [];

    // 1. Append user message immediately
    final userMsg = ChatMessage.userMessage(text);
    state = AsyncData([...current, userMsg]);

    // 2. Append typing indicator
    final withTyping = [...current, userMsg, ChatMessage.typing()];
    state = AsyncData(withTyping);

    try {
      // 3. Get AI response
      final data = await apiService.sendMessage(userId: userId, message: text);
      ref.read(lastChatResponseProvider.notifier).state = data;

      final withoutTyping = [...current, userMsg];

      if (data['success'] == true || data['is_paywall'] == true) {
        final aiMsg = ChatMessage.fromApiResponse(data, text);
        state = AsyncData([...withoutTyping, aiMsg]);
      } else {
        // Error message from AI
        final errorMsg = ChatMessage(
          role: 'assistant',
          content: data['error'] ?? 'Something went wrong. Try again.',
          timestamp: DateTime.now(),
        );
        state = AsyncData([...withoutTyping, errorMsg]);
      }
      return data;
    } catch (e) {
      // Remove typing, show error
      final withoutTyping = [...current, userMsg];
      final errorMsg = ChatMessage(
        role: 'assistant',
        content: '🔴 Connection error. Please check your internet and try again.',
        timestamp: DateTime.now(),
      );
      state = AsyncData([...withoutTyping, errorMsg]);
      return {'success': false, 'error': e.toString()};
    }
  }

  Future<bool> clearChatHistory() async {
    final userId = await LocalStorage.getUserId();
    if (userId == null) return false;

    // Immediately clear local message state so UI resets instantly
    state = const AsyncData([]);

    try {
      final res = await apiService.clearChatHistory(userId);
      if (res['success'] == true) {
        state = const AsyncData([]);
        return true;
      }
    } catch (e) {
      // ignore: avoid_print
      print('[ChatProvider] Error clearing chat history: $e');
    }
    return false;
  }

  void clearMessages() {
    state = const AsyncData([]);
  }
}

// ── Last Chat Response (for level-up / paywall detection) ─────────────────────
final lastChatResponseProvider = StateProvider<Map<String, dynamic>?>((ref) => null);

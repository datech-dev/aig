import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/api_service.dart';
import '../data/local_storage.dart';
import '../services/notification_service.dart';

// ── Notification State ───────────────────────────────────────────────────────

class NotificationState {
  final bool notificationsEnabled;
  final bool soundEnabled;
  final bool proactiveEnabled;
  final bool isSendingTest;

  const NotificationState({
    this.notificationsEnabled = true,
    this.soundEnabled = true,
    this.proactiveEnabled = true,
    this.isSendingTest = false,
  });

  NotificationState copyWith({
    bool? notificationsEnabled,
    bool? soundEnabled,
    bool? proactiveEnabled,
    bool? isSendingTest,
  }) {
    return NotificationState(
      notificationsEnabled: notificationsEnabled ?? this.notificationsEnabled,
      soundEnabled: soundEnabled ?? this.soundEnabled,
      proactiveEnabled: proactiveEnabled ?? this.proactiveEnabled,
      isSendingTest: isSendingTest ?? this.isSendingTest,
    );
  }
}

// ── Notification Provider ────────────────────────────────────────────────────

final notificationProvider =
    StateNotifierProvider<NotificationNotifier, NotificationState>((ref) {
  return NotificationNotifier();
});

class NotificationNotifier extends StateNotifier<NotificationState> {
  NotificationNotifier() : super(const NotificationState()) {
    _loadPreferences();
  }

  Future<void> _loadPreferences() async {
    final notifs = await LocalStorage.isNotificationsEnabled();
    final sound = await LocalStorage.isSoundEnabled();
    final proactive = await LocalStorage.isProactiveEnabled();

    state = state.copyWith(
      notificationsEnabled: notifs,
      soundEnabled: sound,
      proactiveEnabled: proactive,
    );
  }

  Future<void> toggleNotifications(bool enabled) async {
    state = state.copyWith(notificationsEnabled: enabled);
    await LocalStorage.setNotificationsEnabled(enabled);

    if (enabled) {
      await notificationService.requestPermissions();
    } else {
      await notificationService.cancelAll();
    }

    _syncWithBackend();
  }

  Future<void> toggleSound(bool enabled) async {
    state = state.copyWith(soundEnabled: enabled);
    await LocalStorage.setSoundEnabled(enabled);
  }

  Future<void> toggleProactive(bool enabled) async {
    state = state.copyWith(proactiveEnabled: enabled);
    await LocalStorage.setProactiveEnabled(enabled);
    _syncWithBackend();
  }

  Future<void> _syncWithBackend() async {
    try {
      final userId = await LocalStorage.getUserId();
      if (userId == null) return;
      await apiService.updateDeviceToken(
        userId: userId,
        deviceToken: 'local_device_$userId',
        enabled: state.notificationsEnabled && state.proactiveEnabled,
      );
    } catch (e) {
      debugPrint('[NotificationNotifier] Sync error: $e');
    }
  }

  Future<void> sendTestNotification() async {
    state = state.copyWith(isSendingTest: true);

    try {
      final userId = await LocalStorage.getUserId();
      String title = 'Juhi 💕';
      String body =
          'Hey Sweetheart! Just taking a quick break from coding... thinking about you. How is your day going? 🥰';

      // Attempt to get dynamic greeting from backend if available
      if (userId != null) {
        try {
          final res = await apiService.requestTestNotification(userId);
          if (res['success'] == true && res['message'] != null) {
            body = res['message'].toString();
          }
        } catch (_) {}
      }

      await notificationService.showJuhiNotification(
        id: 7777,
        title: title,
        body: body,
        playSound: state.soundEnabled,
        payload: '/chat',
      );
    } catch (e) {
      debugPrint('[NotificationNotifier] Test notification error: $e');
    } finally {
      state = state.copyWith(isSendingTest: false);
    }
  }
}

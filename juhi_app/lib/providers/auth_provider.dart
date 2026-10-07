import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import '../data/local_storage.dart';
import '../data/api_service.dart';

// ── Auth State ────────────────────────────────────────────────────────────────
// true = logged in, false = needs onboarding
final authStateProvider = FutureProvider<bool>((ref) async {
  final userId = await LocalStorage.getUserId();
  return userId != null && userId.isNotEmpty;
});

// ── Current User ID ───────────────────────────────────────────────────────────
final userIdProvider = FutureProvider<String?>((ref) async {
  return await LocalStorage.getUserId();
});

// ── Auth Notifier (for registration) ─────────────────────────────────────────
class AuthNotifier extends AsyncNotifier<bool> {
  @override
  Future<bool> build() async {
    final userId = await LocalStorage.getUserId();
    return userId != null && userId.isNotEmpty;
  }

  /// Register a new user with display name and persist device-based user_id
  Future<bool> register(String displayName) async {
    state = const AsyncLoading();
    try {
      // Generate a device-unique user_id (numeric, app-scoped)
      final uuid = const Uuid().v4();
      // Use last 9 digits of uuid hash as numeric user_id (avoid Telegram collision)
      final numericId = uuid.hashCode.abs() % 900000000 + 100000000;
      final userId = numericId.toString();

      // Persist locally first
      await LocalStorage.saveUserId(userId);
      await LocalStorage.saveUserName(displayName);

      // Register on the backend
      await apiService.auth(
        userId: userId,
        username: displayName.toLowerCase().replaceAll(' ', '_'),
        firstName: displayName,
      );

      await LocalStorage.setOnboardingDone(true);
      state = const AsyncData(true);
      return true;
    } catch (e) {
      state = AsyncError(e, StackTrace.current);
      // Even on API error, keep locally registered so app still works offline-first
      final userId = await LocalStorage.getUserId();
      if (userId != null) {
        state = const AsyncData(true);
        return true;
      }
      return false;
    }
  }

  Future<void> logout() async {
    await LocalStorage.clearAll();
    state = const AsyncData(false);
  }
}

final authNotifierProvider =
    AsyncNotifierProvider<AuthNotifier, bool>(AuthNotifier.new);

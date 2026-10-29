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
      ref.invalidate(authStateProvider);
      ref.invalidate(userIdProvider);
      state = const AsyncData(true);
      return true;
    } catch (e) {
      state = AsyncError(e, StackTrace.current);
      final userId = await LocalStorage.getUserId();
      if (userId != null) {
        ref.invalidate(authStateProvider);
        ref.invalidate(userIdProvider);
        state = const AsyncData(true);
        return true;
      }
      return false;
    }
  }

  /// Request OTP for mobile number authentication
  Future<Map<String, dynamic>> sendOtp(String phone) async {
    return await apiService.sendOtp(phone);
  }

  /// Verify OTP and log in with phone number
  Future<bool> verifyOtpAndLogin({
    required String phone,
    required String otp,
    String? name,
  }) async {
    state = const AsyncLoading();
    try {
      final res = await apiService.verifyOtp(
        phone: phone,
        otp: otp,
        name: name,
      );

      if (res['success'] == true) {
        final userId = res['user_id'].toString();
        final firstName = res['first_name'] as String? ?? name ?? 'User';

        await LocalStorage.saveUserId(userId);
        await LocalStorage.saveUserName(firstName);
        await LocalStorage.setOnboardingDone(true);

        ref.invalidate(authStateProvider);
        ref.invalidate(userIdProvider);
        state = const AsyncData(true);
        return true;
      } else {
        state = AsyncError(res['error'] ?? 'OTP verification failed', StackTrace.current);
        return false;
      }
    } catch (e) {
      state = AsyncError(e, StackTrace.current);
      return false;
    }
  }

  /// Authenticate and log in with Google account
  Future<bool> loginWithGoogle({
    required String email,
    String? googleId,
    String? displayName,
  }) async {
    state = const AsyncLoading();
    try {
      final res = await apiService.loginWithGoogle(
        email: email,
        googleId: googleId,
        displayName: displayName,
      );

      if (res['success'] == true) {
        final userId = res['user_id'].toString();
        final firstName = res['first_name'] as String? ?? displayName ?? 'User';

        await LocalStorage.saveUserId(userId);
        await LocalStorage.saveUserName(firstName);
        await LocalStorage.setOnboardingDone(true);

        ref.invalidate(authStateProvider);
        ref.invalidate(userIdProvider);
        state = const AsyncData(true);
        return true;
      } else {
        state = AsyncError(res['error'] ?? 'Google sign-in failed', StackTrace.current);
        return false;
      }
    } catch (e) {
      state = AsyncError(e, StackTrace.current);
      return false;
    }
  }

  Future<void> logout() async {
    await LocalStorage.clearAll();
    ref.invalidate(authStateProvider);
    ref.invalidate(userIdProvider);
    state = const AsyncData(false);
  }
}

final authNotifierProvider =
    AsyncNotifierProvider<AuthNotifier, bool>(AuthNotifier.new);

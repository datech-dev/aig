import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/constants.dart';

class LocalStorage {
  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  // ── User ID (secure) ──────────────────────────────────────────────────────
  static Future<void> saveUserId(String userId) async {
    await _storage.write(key: AppConstants.keyUserId, value: userId);
  }

  static Future<String?> getUserId() async {
    return await _storage.read(key: AppConstants.keyUserId);
  }

  static Future<void> deleteUserId() async {
    await _storage.delete(key: AppConstants.keyUserId);
  }

  // ── Preferences ───────────────────────────────────────────────────────────
  static Future<void> setOnboardingDone(bool done) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(AppConstants.keyOnboardingDone, done);
  }

  static Future<bool> isOnboardingDone() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(AppConstants.keyOnboardingDone) ?? false;
  }

  static Future<void> saveUserName(String name) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConstants.keyUserName, name);
  }

  static Future<String?> getUserName() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(AppConstants.keyUserName);
  }

  // ── Notification Preferences ─────────────────────────────────────────────
  static const String keyNotificationsEnabled = 'notifications_enabled';
  static const String keySoundEnabled = 'notification_sound_enabled';
  static const String keyProactiveEnabled = 'proactive_messages_enabled';

  static Future<void> setNotificationsEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(keyNotificationsEnabled, enabled);
  }

  static Future<bool> isNotificationsEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(keyNotificationsEnabled) ?? true;
  }

  static Future<void> setSoundEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(keySoundEnabled, enabled);
  }

  static Future<bool> isSoundEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(keySoundEnabled) ?? true;
  }

  static Future<void> setProactiveEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(keyProactiveEnabled, enabled);
  }

  static Future<bool> isProactiveEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(keyProactiveEnabled) ?? true;
  }

  // ── Clear all ─────────────────────────────────────────────────────────────
  static Future<void> clearAll() async {
    await _storage.deleteAll();
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
  }
}

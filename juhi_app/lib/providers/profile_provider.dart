import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/api_service.dart';
import '../data/local_storage.dart';
import '../models/user_profile.dart';

// ── Profile Provider ──────────────────────────────────────────────────────────
final profileProvider = AsyncNotifierProvider<ProfileNotifier, UserProfile?>(
  ProfileNotifier.new,
);

class ProfileNotifier extends AsyncNotifier<UserProfile?> {
  @override
  Future<UserProfile?> build() async {
    return await _fetchProfile();
  }

  Future<UserProfile?> _fetchProfile() async {
    final userId = await LocalStorage.getUserId();
    if (userId == null) return null;

    try {
      final data = await apiService.getProfile(userId);
      if (data['success'] == true) {
        return UserProfile.fromJson(data);
      }
    } catch (e) {
      // ignore: avoid_print
      print('[ProfileProvider] Error fetching profile: $e');
    }
    return null;
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = AsyncData(await _fetchProfile());
  }

  void updateLocally(UserProfile updated) {
    state = AsyncData(updated);
  }
}

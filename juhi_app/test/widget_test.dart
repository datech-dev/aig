import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:juhi_app/core/theme.dart';
import 'package:juhi_app/core/constants.dart';
import 'package:juhi_app/models/chat_message.dart';
import 'package:juhi_app/models/user_profile.dart';
import 'package:juhi_app/models/memory_item.dart';
import 'package:juhi_app/providers/notification_provider.dart';
import 'package:juhi_app/services/notification_service.dart';

void main() {
  group('Juhi App Phase 1 Core Tests', () {
    test('AppTheme colors and gradients configured correctly', () {
      expect(AppTheme.primary, const Color(AppConstants.colorPrimary));
      expect(AppTheme.secondary, const Color(AppConstants.colorSecondary));
      expect(AppTheme.background, const Color(AppConstants.colorBackground));
      expect(AppTheme.primaryGradient.colors.length, 2);
    });

    test('ChatMessage JSON serialization works', () {
      final msg = ChatMessage.fromJson({
        'role': 'assistant',
        'content': 'Hello from Juhi 💖',
        'has_image': false,
        'has_gif': false,
        'timestamp': '2026-10-07T12:00:00Z',
      });
      expect(msg.isJuhi, true);
      expect(msg.content, 'Hello from Juhi 💖');
      expect(msg.isUser, false);
      expect(msg.formattedTime.isNotEmpty, true);
    });

    test('UserProfile JSON serialization works', () {
      final profile = UserProfile.fromJson({
        'user_id': '123456789',
        'xp': 150,
        'level': 2,
        'title': 'Crush',
        'mode': 'caring',
        'image_credits': 10,
        'is_subscribed': false,
      });
      expect(profile.userId, '123456789');
      expect(profile.level, 2);
      expect(profile.levelTitle, 'Crush');
      expect(profile.affection, 150);
      expect(profile.affectionPercent, 0);
      expect(profile.imageCredits, 10);
      expect(profile.isSubscribed, false);
      expect(profile.hasImageCredits, true);
    });
  });

  group('Juhi App Phase 2 Chat & Media Tests', () {
    test('ChatMessage parses GIF correctly and formats URL', () {
      final gifMsg = ChatMessage.fromApiResponse({
        'reply': 'Aww you make me blush! 💕',
        'has_image': false,
        'has_gif': true,
        'gif_name': 'blush',
      }, 'You are cute');

      expect(gifMsg.hasGif, true);
      expect(gifMsg.gifName, 'blush');
      expect(gifMsg.gifUrl, '${AppConstants.baseUrl}/gifs/blush.gif');
      expect(gifMsg.content, 'Aww you make me blush! 💕');
    });

    test('ChatMessage parses Image generation prompts correctly', () {
      final imgMsg = ChatMessage.fromApiResponse({
        'reply': 'Here is a selfie from my room! 📸',
        'has_image': true,
        'image_prompt': 'Juhi, casual selfie, wearing stylish hoodie, smiling',
        'has_gif': false,
      }, 'Send me a selfie');

      expect(imgMsg.hasImage, true);
      expect(imgMsg.imagePrompt, 'Juhi, casual selfie, wearing stylish hoodie, smiling');
    });

    test('ChatMessage handles paywall response', () {
      final paywallMsg = ChatMessage.fromApiResponse({
        'reply': 'Our free trial time just ran out for today! 🥺',
        'is_paywall': true,
        'has_image': false,
        'has_gif': false,
      }, 'Hey');

      expect(paywallMsg.isPaywall, true);
      expect(paywallMsg.content.contains('free trial'), true);
    });
  });

  group('Juhi App Phase 4 Memory Vault Tests', () {
    test('MemoryItem auto-classifies preferences, career, and routine correctly', () {
      final coffeeMem = MemoryItem.fromText('User loves black coffee in the morning');
      expect(coffeeMem.category, 'Preferences');
      expect(coffeeMem.icon, '☕');

      final techMem = MemoryItem.fromText('User works as a software engineer in Bangalore');
      expect(techMem.category, 'Career');
      expect(techMem.icon, '💼');

      final gymMem = MemoryItem.fromText('User goes to the gym every morning');
      expect(gymMem.category, 'Routine');
      expect(gymMem.icon, '⏰');

      final romanticMem = MemoryItem.fromText('User said they are in love with Juhi and she is their romantic crush');
      expect(romanticMem.category, 'Romance');
      expect(romanticMem.icon, '💖');

      final generalMem = MemoryItem.fromText('User has a pet dog named Bruno');
      expect(generalMem.category, 'Personal');
      expect(generalMem.icon, '🌸');
    });
  });

  group('Juhi App Phase 5 Store & Payments Tests', () {
    test('Pricing constants match required pricing values', () {
      expect(AppConstants.price1Day, 49);
      expect(AppConstants.price1Week, 199);
      expect(AppConstants.price1Month, 499);
      expect(AppConstants.priceImages, 49);
    });

    test('UserProfile formats subscription expiry accurately', () {
      final now = DateTime.now();
      final futureDate = now.add(const Duration(days: 3, hours: 4));
      final pastDate = now.subtract(const Duration(hours: 2));

      final activeProfile = UserProfile.fromJson({
        'user_id': '101',
        'is_subscribed': true,
        'chat_expires_at': futureDate.toIso8601String(),
      });
      expect(activeProfile.isSubscribed, true);
      expect(activeProfile.formattedExpiry?.contains('remaining'), true);
      expect(activeProfile.formattedExpiry?.contains('3d'), true);

      final expiredProfile = UserProfile.fromJson({
        'user_id': '102',
        'is_subscribed': false,
        'chat_expires_at': pastDate.toIso8601String(),
      });
      expect(expiredProfile.formattedExpiry, 'Expired');

      final freeProfile = UserProfile.fromJson({
        'user_id': '103',
        'is_subscribed': false,
      });
      expect(freeProfile.formattedExpiry, null);
    });
  });

  group('Juhi App Phase 6 Notifications Tests', () {
    test('NotificationState defaults and copyWith work properly', () {
      const state = NotificationState();
      expect(state.notificationsEnabled, true);
      expect(state.soundEnabled, true);
      expect(state.proactiveEnabled, true);
      expect(state.isSendingTest, false);

      final updated = state.copyWith(
        notificationsEnabled: false,
        soundEnabled: false,
        isSendingTest: true,
      );
      expect(updated.notificationsEnabled, false);
      expect(updated.soundEnabled, false);
      expect(updated.proactiveEnabled, true);
      expect(updated.isSendingTest, true);
    });

    test('NotificationService channel constants and endpoints configured', () {
      expect(NotificationService.channelId, 'juhi_proactive_channel');
      expect(NotificationService.channelName.contains('Juhi'), true);
      expect(AppConstants.apiDeviceToken, '/api/device-token');
      expect(AppConstants.apiTestNotification, '/api/notifications/test');
    });
  });
}



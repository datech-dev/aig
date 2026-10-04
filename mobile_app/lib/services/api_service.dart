import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';
import '../models/user_profile.dart';
import '../models/chat_message.dart';

class ApiService {
  // Authenticate / register user
  static Future<bool> authUser(int userId, String username, String firstName) async {
    try {
      final response = await http.post(
        Uri.parse(ApiConfig.authUrl),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'user_id': userId,
          'username': username,
          'first_name': firstName,
        }),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['success'] == true;
      }
    } catch (e) {
      print('Auth error: $e');
    }
    return false;
  }

  // Fetch user profile
  static Future<UserProfile?> fetchProfile(int userId) async {
    try {
      final response = await http.get(
        Uri.parse('${ApiConfig.profileUrl}?user_id=$userId'),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          return UserProfile.fromJson(data);
        }
      }
    } catch (e) {
      print('Fetch profile error: $e');
    }
    return null;
  }

  // Fetch chat history
  static Future<List<ChatMessage>> fetchHistory(int userId) async {
    try {
      final response = await http.get(
        Uri.parse('${ApiConfig.historyUrl}?user_id=$userId'),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true && data['history'] != null) {
          final List list = data['history'];
          return list.map((item) => ChatMessage.fromJson(item)).toList();
        }
      }
    } catch (e) {
      print('Fetch history error: $e');
    }
    return [];
  }

  // Send message
  static Future<Map<String, dynamic>> sendMessage(int userId, String message) async {
    try {
      final response = await http.post(
        Uri.parse(ApiConfig.chatUrl),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'user_id': userId,
          'message': message,
        }),
      );
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
    } catch (e) {
      print('Send message error: $e');
    }
    return {
      'success': false,
      'error': 'Network error. Please check connection.',
      'reply': '⚠️ Connection error. Please check your internet and try again.'
    };
  }

  // Toggle chat mode (Caring Best Friend <-> Intimate Girlfriend)
  static Future<String?> toggleMode(int userId) async {
    try {
      final response = await http.post(
        Uri.parse(ApiConfig.toggleModeUrl),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'user_id': userId}),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          return data['chat_mode'];
        }
      }
    } catch (e) {
      print('Toggle mode error: $e');
    }
    return null;
  }

  // Fetch memories
  static Future<List<String>> fetchMemories(int userId) async {
    try {
      final response = await http.get(
        Uri.parse('${ApiConfig.memoriesUrl}?user_id=$userId'),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true && data['memories'] != null) {
          return List<String>.from(data['memories']);
        }
      }
    } catch (e) {
      print('Fetch memories error: $e');
    }
    return [];
  }

  // Clear memory bank
  static Future<bool> clearMemories(int userId) async {
    try {
      final response = await http.post(
        Uri.parse(ApiConfig.memoriesUrl),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'user_id': userId, 'action': 'clear'}),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['success'] == true;
      }
    } catch (e) {
      print('Clear memories error: $e');
    }
    return false;
  }
}

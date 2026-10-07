import 'package:intl/intl.dart';
import '../core/constants.dart';

class ChatMessage {
  final String role; // 'user' | 'assistant'
  final String content;
  final DateTime timestamp;
  final bool hasImage;
  final String? imagePrompt;
  final bool hasGif;
  final String? gifName;
  final bool isLoading;
  final bool isPaywall;

  const ChatMessage({
    required this.role,
    required this.content,
    required this.timestamp,
    this.hasImage = false,
    this.imagePrompt,
    this.hasGif = false,
    this.gifName,
    this.isLoading = false,
    this.isPaywall = false,
  });

  bool get isUser => role == 'user';
  bool get isAssistant => role == 'assistant';
  bool get isJuhi => role == 'assistant';

  String get formattedTime {
    return DateFormat('h:mm a').format(timestamp);
  }

  String? get gifUrl {
    if (!hasGif || gifName == null || gifName!.isEmpty) return null;
    final name = gifName!.endsWith('.gif') ? gifName! : '$gifName.gif';
    return '${AppConstants.baseUrl}/gifs/$name';
  }

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      role: json['role'] ?? 'user',
      content: json['content'] ?? '',
      timestamp: json['timestamp'] != null && json['timestamp'].toString().isNotEmpty
          ? DateTime.tryParse(json['timestamp'].toString()) ?? DateTime.now()
          : DateTime.now(),
      hasImage: json['has_image'] ?? false,
      imagePrompt: json['image_prompt'],
      hasGif: json['has_gif'] ?? false,
      gifName: json['gif_name'],
      isPaywall: json['is_paywall'] ?? false,
    );
  }

  factory ChatMessage.typing() {
    return ChatMessage(
      role: 'assistant',
      content: '',
      timestamp: DateTime.now(),
      isLoading: true,
    );
  }

  factory ChatMessage.fromApiResponse(Map<String, dynamic> json, String userMessage) {
    return ChatMessage(
      role: 'assistant',
      content: json['reply'] ?? '',
      timestamp: DateTime.now(),
      hasImage: json['has_image'] ?? false,
      imagePrompt: json['image_prompt'],
      hasGif: json['has_gif'] ?? false,
      gifName: json['gif_name'],
      isPaywall: json['is_paywall'] ?? false,
    );
  }

  static ChatMessage userMessage(String text) {
    return ChatMessage(
      role: 'user',
      content: text,
      timestamp: DateTime.now(),
    );
  }
}

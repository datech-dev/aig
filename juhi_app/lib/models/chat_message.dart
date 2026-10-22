import 'package:intl/intl.dart';
import '../core/constants.dart';

class ChatMessage {
  final String role; // 'user' | 'assistant'
  final String content;
  final DateTime timestamp;
  final bool hasImage;
  final String? imagePrompt;
  final String? rawImageUrl;
  final bool hasGif;
  final String? gifName;
  final String? rawGifUrl;
  final bool isLoading;
  final bool isPaywall;

  const ChatMessage({
    required this.role,
    required this.content,
    required this.timestamp,
    this.hasImage = false,
    this.imagePrompt,
    this.rawImageUrl,
    this.hasGif = false,
    this.gifName,
    this.rawGifUrl,
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
    if (!hasGif) return null;
    if (rawGifUrl != null && rawGifUrl!.trim().isNotEmpty) {
      if (rawGifUrl!.startsWith('http://') || rawGifUrl!.startsWith('https://')) {
        return rawGifUrl;
      }
      final path = rawGifUrl!.startsWith('/') ? rawGifUrl! : '/$rawGifUrl';
      return '${AppConstants.baseUrl}$path';
    }
    if (gifName == null || gifName!.trim().isEmpty) return null;
    final clean = Uri.encodeComponent(gifName!.trim().toLowerCase().replaceAll('.gif', ''));
    return '${AppConstants.baseUrl}/gifs/$clean.gif';
  }

  String? get imageUrl {
    if (!hasImage || rawImageUrl == null || rawImageUrl!.trim().isEmpty) return null;
    if (rawImageUrl!.startsWith('http://') || rawImageUrl!.startsWith('https://')) {
      return rawImageUrl;
    }
    final path = rawImageUrl!.startsWith('/') ? rawImageUrl! : '/$rawImageUrl';
    return '${AppConstants.baseUrl}$path';
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
      rawImageUrl: json['image_url'],
      hasGif: json['has_gif'] ?? false,
      gifName: json['gif_name'],
      rawGifUrl: json['gif_url'],
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
      rawImageUrl: json['image_url'],
      hasGif: json['has_gif'] ?? false,
      gifName: json['gif_name'],
      rawGifUrl: json['gif_url'],
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

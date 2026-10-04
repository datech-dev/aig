class ChatMessage {
  final String role; // 'user' or 'assistant'
  final String content;
  final String? timestamp;
  final bool hasImage;
  final String? imagePrompt;
  final bool hasGif;
  final String? gifName;
  final bool isPaywall;

  ChatMessage({
    required this.role,
    required this.content,
    this.timestamp,
    this.hasImage = false,
    this.imagePrompt,
    this.hasGif = false,
    this.gifName,
    this.isPaywall = false,
  });

  bool get isUser => role == 'user';

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      role: json['role'] ?? 'assistant',
      content: json['content'] ?? '',
      timestamp: json['timestamp'],
      hasImage: json['has_image'] ?? false,
      imagePrompt: json['image_prompt'],
      hasGif: json['has_gif'] ?? false,
      gifName: json['gif_name'],
      isPaywall: json['is_paywall'] ?? false,
    );
  }
}

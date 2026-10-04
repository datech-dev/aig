class UserProfile {
  final int userId;
  final String partnerName;
  final String partnerTagline;
  final String chatMode; // 'normal' or 'intimate'
  final String chatModeLabel;
  final int level;
  final String title;
  final int xp;
  final int percent;
  final String userNickname;
  final String aiNickname;
  final int memoryCount;
  final bool isSubscribed;
  final int remainingFreeMessages;
  final int imageCredits;

  UserProfile({
    required this.userId,
    required this.partnerName,
    required this.partnerTagline,
    required this.chatMode,
    required this.chatModeLabel,
    required this.level,
    required this.title,
    required this.xp,
    required this.percent,
    required this.userNickname,
    required this.aiNickname,
    required this.memoryCount,
    required this.isSubscribed,
    required this.remainingFreeMessages,
    required this.imageCredits,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      userId: json['user_id'] ?? 0,
      partnerName: json['partner_name'] ?? 'Karin',
      partnerTagline: json['partner_tagline'] ?? 'Alone at Home',
      chatMode: json['chat_mode'] ?? 'normal',
      chatModeLabel: json['chat_mode_label'] ?? 'Caring Best Friend',
      level: json['level'] ?? 1,
      title: json['title'] ?? 'Acquaintances',
      xp: json['xp'] ?? 0,
      percent: json['percent'] ?? 0,
      userNickname: json['user_nickname'] ?? 'User',
      aiNickname: json['ai_nickname'] ?? 'Karin',
      memoryCount: json['memory_count'] ?? 0,
      isSubscribed: json['is_subscribed'] ?? false,
      remainingFreeMessages: json['remaining_free_messages'] ?? 10,
      imageCredits: json['image_credits'] ?? 0,
    );
  }
}

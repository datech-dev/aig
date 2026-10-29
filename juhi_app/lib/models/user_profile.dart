class UserProfile {
  final String userId;
  final String partnerName;
  final String partnerTagline;
  final String chatMode;
  final String chatModeLabel;
  final int level;
  final String levelTitle;
  final int xp;
  final int xpPercent;
  final String userNickname;
  final String aiNickname;
  final int memoryCount;
  final bool isSubscribed;
  final int remainingFreeMessages;
  final int imageCredits;
  final String? chatExpiresAt;
  final String? expiresAtIst;
  final String? expiryDateStr;
  final String? expiryTimeStr;
  final String? subscriptionRemainingText;
  final String? subscriptionPlan;
  final int voiceCallSeconds;

  const UserProfile({
    required this.userId,
    required this.partnerName,
    required this.partnerTagline,
    required this.chatMode,
    required this.chatModeLabel,
    required this.level,
    required this.levelTitle,
    required this.xp,
    required this.xpPercent,
    required this.userNickname,
    required this.aiNickname,
    required this.memoryCount,
    required this.isSubscribed,
    required this.remainingFreeMessages,
    required this.imageCredits,
    this.voiceCallSeconds = 0,
    this.chatExpiresAt,
    this.expiresAtIst,
    this.expiryDateStr,
    this.expiryTimeStr,
    this.subscriptionRemainingText,
    this.subscriptionPlan,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      userId: json['user_id'].toString(),
      partnerName: json['partner_name'] ?? 'Juhi',
      partnerTagline: json['partner_tagline'] ?? '💻 Bangalore Techie & Girlfriend',
      chatMode: json['chat_mode'] ?? 'normal',
      chatModeLabel: json['chat_mode_label'] ?? 'Caring Best Friend',
      level: json['level'] ?? 1,
      levelTitle: json['title'] ?? 'Acquaintances',
      xp: json['xp'] ?? 0,
      xpPercent: json['percent'] ?? 0,
      userNickname: json['user_nickname'] ?? 'User',
      aiNickname: json['ai_nickname'] ?? 'Juhi',
      memoryCount: json['memory_count'] ?? 0,
      isSubscribed: json['is_subscribed'] ?? false,
      remainingFreeMessages: json['remaining_free_messages'] ?? 10,
      imageCredits: json['image_credits'] ?? 0,
      voiceCallSeconds: (json['voice_call_seconds'] as num?)?.toInt() ?? 0,
      chatExpiresAt: json['chat_expires_at'],
      expiresAtIst: json['expires_at_ist'],
      expiryDateStr: json['expiry_date_str'],
      expiryTimeStr: json['expiry_time_str'],
      subscriptionRemainingText: json['subscription_remaining_text'],
      subscriptionPlan: json['subscription_plan'],
    );
  }

  bool get isIntimateMode => chatMode == 'intimate';
  bool get hasImageCredits => imageCredits > 0;
  bool get hasVoiceBalance => voiceCallSeconds > 0;
  int get affection => xp;
  int get affectionPercent => xpPercent;

  String get formattedVoiceBalance {
    final mins = voiceCallSeconds ~/ 60;
    final secs = voiceCallSeconds % 60;
    return '${mins.toString().padLeft(2, '0')}:${secs.toString().padLeft(2, '0')}';
  }

  DateTime? get chatExpiresAtDate {
    if (chatExpiresAt == null || chatExpiresAt!.isEmpty) return null;
    return DateTime.tryParse(chatExpiresAt!);
  }

  String? get formattedExpiry {
    if (subscriptionRemainingText != null && subscriptionRemainingText!.isNotEmpty) {
      if (subscriptionRemainingText == 'Expired') return 'Expired';
      return '$subscriptionRemainingText remaining';
    }
    final exp = chatExpiresAtDate;
    if (exp == null) return null;
    final now = DateTime.now();
    final diff = exp.difference(now);
    if (diff.isNegative) return 'Expired';
    if (diff.inDays > 0) return '${diff.inDays}d ${diff.inHours % 24}h remaining';
    if (diff.inHours > 0) return '${diff.inHours}h ${diff.inMinutes % 60}m remaining';
    return '${diff.inMinutes}m remaining';
  }

  /// User-friendly, authoritative expiration date and time formatted in IST
  String get formattedExpiryDate {
    if (expiryDateStr != null && expiryDateStr!.isNotEmpty) {
      if (expiryTimeStr != null && expiryTimeStr!.isNotEmpty) {
        return '$expiryDateStr ($expiryTimeStr)';
      }
      return expiryDateStr!;
    }
    if (expiresAtIst != null && expiresAtIst!.isNotEmpty) {
      return expiresAtIst!;
    }
    final exp = chatExpiresAtDate;
    if (exp != null) {
      return '${exp.day.toString().padLeft(2, '0')}/${exp.month.toString().padLeft(2, '0')}/${exp.year}';
    }
    return 'Active';
  }

  UserProfile copyWith({
    bool? isSubscribed,
    int? remainingFreeMessages,
    int? imageCredits,
    int? xp,
    int? xpPercent,
    int? level,
    String? levelTitle,
    String? chatMode,
    String? chatModeLabel,
    int? memoryCount,
    String? chatExpiresAt,
    String? expiresAtIst,
    String? expiryDateStr,
    String? expiryTimeStr,
    String? subscriptionRemainingText,
    String? subscriptionPlan,
    int? voiceCallSeconds,
  }) {
    return UserProfile(
      userId: userId,
      partnerName: partnerName,
      partnerTagline: partnerTagline,
      chatMode: chatMode ?? this.chatMode,
      chatModeLabel: chatModeLabel ?? this.chatModeLabel,
      level: level ?? this.level,
      levelTitle: levelTitle ?? this.levelTitle,
      xp: xp ?? this.xp,
      xpPercent: xpPercent ?? this.xpPercent,
      userNickname: userNickname,
      aiNickname: aiNickname,
      memoryCount: memoryCount ?? this.memoryCount,
      isSubscribed: isSubscribed ?? this.isSubscribed,
      remainingFreeMessages: remainingFreeMessages ?? this.remainingFreeMessages,
      imageCredits: imageCredits ?? this.imageCredits,
      voiceCallSeconds: voiceCallSeconds ?? this.voiceCallSeconds,
      chatExpiresAt: chatExpiresAt ?? this.chatExpiresAt,
      expiresAtIst: expiresAtIst ?? this.expiresAtIst,
      expiryDateStr: expiryDateStr ?? this.expiryDateStr,
      expiryTimeStr: expiryTimeStr ?? this.expiryTimeStr,
      subscriptionRemainingText: subscriptionRemainingText ?? this.subscriptionRemainingText,
      subscriptionPlan: subscriptionPlan ?? this.subscriptionPlan,
    );
  }
}

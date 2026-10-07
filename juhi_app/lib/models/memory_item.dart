class MemoryItem {
  final String text;
  final String category;
  final String icon;

  const MemoryItem({
    required this.text,
    required this.category,
    required this.icon,
  });

  factory MemoryItem.fromText(String rawText) {
    final lower = rawText.toLowerCase();

    // Check specific preferences first (food, drinks, music, hobbies)
    if (lower.contains('coffee') ||
        lower.contains('tea') ||
        lower.contains('pizza') ||
        lower.contains('food') ||
        lower.contains('favorite') ||
        lower.contains('favourite') ||
        lower.contains('drink') ||
        lower.contains('movie') ||
        lower.contains('music') ||
        lower.contains('song')) {
      return MemoryItem(
        text: rawText,
        category: 'Preferences',
        icon: '☕',
      );
    } else if (lower.contains('romantic') ||
        lower.contains('girlfriend') ||
        lower.contains('in love') ||
        lower.contains('crush') ||
        lower.contains('kiss') ||
        lower.contains('dating') ||
        lower.contains('relationship') ||
        lower.contains('soulmate')) {
      return MemoryItem(
        text: rawText,
        category: 'Romance',
        icon: '💖',
      );
    } else if (lower.contains('work') ||
        lower.contains('job') ||
        lower.contains('code') ||
        lower.contains('tech') ||
        lower.contains('engineer') ||
        lower.contains('developer') ||
        lower.contains('office') ||
        lower.contains('company')) {
      return MemoryItem(
        text: rawText,
        category: 'Career',
        icon: '💼',
      );
    } else if (lower.contains('gym') ||
        lower.contains('workout') ||
        lower.contains('sleep') ||
        lower.contains('morning routine') ||
        lower.contains('routine') ||
        lower.contains('wake up')) {
      return MemoryItem(
        text: rawText,
        category: 'Routine',
        icon: '⏰',
      );
    } else {
      return MemoryItem(
        text: rawText,
        category: 'Personal',
        icon: '🌸',
      );
    }
  }
}

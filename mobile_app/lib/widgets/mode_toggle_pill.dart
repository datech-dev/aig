import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class ModeTogglePill extends StatelessWidget {
  final String chatMode; // 'normal' or 'intimate'
  final VoidCallback onToggle;

  const ModeTogglePill({
    Key? key,
    required this.chatMode,
    required this.onToggle,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final isNormal = chatMode == 'normal';
    return GestureDetector(
      onTap: onToggle,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 300),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isNormal ? Colors.pinkAccent.withOpacity(0.15) : Colors.redAccent.withOpacity(0.2),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isNormal ? AppTheme.accentCyan : AppTheme.primaryRose,
            width: 1.2,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              isNormal ? '🌸 Best Friend' : '🔥 Intimate',
              style: TextStyle(
                color: isNormal ? AppTheme.accentCyan : AppTheme.primaryRose,
                fontSize: 13,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(width: 4),
            Icon(
              Icons.swap_horiz_rounded,
              size: 16,
              color: isNormal ? AppTheme.accentCyan : AppTheme.primaryRose,
            )
          ],
        ),
      ),
    );
  }
}

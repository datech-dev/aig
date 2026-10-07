import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/theme.dart';

class ChatInputBar extends StatefulWidget {
  final Future<void> Function(String) onSend;

  const ChatInputBar({super.key, required this.onSend});

  @override
  State<ChatInputBar> createState() => _ChatInputBarState();
}

class _ChatInputBarState extends State<ChatInputBar> {
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();
  bool _hasText = false;
  bool _isSending = false;

  @override
  void initState() {
    super.initState();
    _controller.addListener(() {
      final has = _controller.text.trim().isNotEmpty;
      if (has != _hasText) setState(() => _hasText = has);
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _isSending) return;

    HapticFeedback.lightImpact();
    setState(() => _isSending = true);
    _controller.clear();

    try {
      await widget.onSend(text);
    } finally {
      if (mounted) setState(() => _isSending = false);
    }
  }

  void _showSelfiePrompts() {
    HapticFeedback.selectionClick();
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          border: const Border(
            top: BorderSide(color: AppTheme.border, width: 1),
          ),
        ),
        child: SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppTheme.primary.withValues(alpha: 0.15),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.camera_alt_rounded, color: AppTheme.primary, size: 20),
                  ),
                  const SizedBox(width: 12),
                  const Text(
                    'Ask Juhi for a Picture 📸',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              ...[
                'Juhi, can you send me a cute selfie? 💖',
                'Show me what you are doing right now ✨',
                'Can I see your pretty smile today? 😊',
                'Send me a cozy evening picture! 🌙',
              ].map((prompt) => InkWell(
                    onTap: () {
                      Navigator.pop(ctx);
                      _controller.text = prompt;
                      _focusNode.requestFocus();
                    },
                    borderRadius: BorderRadius.circular(12),
                    child: Container(
                      width: double.infinity,
                      margin: const EdgeInsets.only(bottom: 8),
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      decoration: BoxDecoration(
                        color: AppTheme.card,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppTheme.border, width: 0.5),
                      ),
                      child: Text(
                        prompt,
                        style: const TextStyle(color: Colors.white, fontSize: 14),
                      ),
                    ),
                  )),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surface,
        border: const Border(
          top: BorderSide(color: AppTheme.border, width: 0.5),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(10, 8, 12, 10),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              // Photo / Selfie Prompt Button
              Container(
                margin: const EdgeInsets.only(bottom: 2),
                child: IconButton(
                  onPressed: _showSelfiePrompts,
                  icon: const Icon(Icons.camera_alt_rounded),
                  color: AppTheme.primary,
                  iconSize: 22,
                  tooltip: 'Ask for a selfie',
                ),
              ),

              // Text input field
              Expanded(
                child: Container(
                  constraints: const BoxConstraints(maxHeight: 120),
                  decoration: BoxDecoration(
                    color: AppTheme.card,
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(
                      color: _hasText
                          ? AppTheme.primary.withValues(alpha: 0.5)
                          : AppTheme.border,
                      width: 1,
                    ),
                  ),
                  child: TextField(
                    controller: _controller,
                    focusNode: _focusNode,
                    maxLines: 4,
                    minLines: 1,
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _send(),
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 15,
                      height: 1.4,
                    ),
                    decoration: InputDecoration(
                      hintText: 'Talk to Juhi...',
                      hintStyle: TextStyle(
                        color: AppTheme.textSecondary,
                        fontSize: 15,
                      ),
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 10,
                      ),
                    ),
                  ),
                ),
              ),

              const SizedBox(width: 8),

              // Animated Send button
              AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: _hasText ? AppTheme.primaryGradient : null,
                  color: _hasText ? null : AppTheme.card,
                  boxShadow: _hasText ? AppTheme.glowShadow(blur: 10) : null,
                  border: _hasText
                      ? null
                      : Border.all(color: AppTheme.border, width: 0.5),
                ),
                child: IconButton(
                  onPressed: _hasText && !_isSending ? _send : null,
                  icon: _isSending
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : Icon(
                          Icons.send_rounded,
                          color: _hasText
                              ? Colors.white
                              : AppTheme.textSecondary,
                          size: 19,
                        ),
                  padding: EdgeInsets.zero,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

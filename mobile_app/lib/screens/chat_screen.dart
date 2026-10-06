import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/user_profile.dart';
import '../models/chat_message.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/xp_bar.dart';
import '../widgets/mode_toggle_pill.dart';
import '../widgets/memory_bank_sheet.dart';
import '../widgets/paywall_sheet.dart';

class ChatScreen extends StatefulWidget {
  final int userId;

  const ChatScreen({Key? key, required this.userId}) : super(key: key);

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  UserProfile? _profile;
  List<ChatMessage> _messages = [];
  bool _isLoading = true;
  bool _isSending = false;
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final profile = await ApiService.fetchProfile(widget.userId);
    final history = await ApiService.fetchHistory(widget.userId);
    if (mounted) {
      setState(() {
        _profile = profile;
        _messages = history;
        _isLoading = false;
      });
      _scrollToBottom();
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _handleSend() async {
    final text = _inputController.text.trim();
    if (text.isEmpty || _isSending) return;

    _inputController.clear();
    final userMsg = ChatMessage(role: 'user', content: text);

    setState(() {
      _messages.add(userMsg);
      _isSending = true;
    });
    _scrollToBottom();

    final res = await ApiService.sendMessage(widget.userId, text);
    if (!mounted) return;

    setState(() => _isSending = false);

    if (res['is_paywall'] == true) {
      _showPaywall(res['reply'] ?? 'Free trial expired. Please unlock chat pass.');
    } else if (res['success'] == true) {
      final replyText = res['reply'] ?? '';
      final assistantMsg = ChatMessage(
        role: 'assistant',
        content: replyText,
        hasImage: res['has_image'] ?? false,
        imagePrompt: res['image_prompt'],
        hasGif: res['has_gif'] ?? false,
        gifName: res['gif_name'],
      );
      setState(() {
        _messages.add(assistantMsg);
      });
      _scrollToBottom();
      _refreshProfile();

      if (res['leveled_up'] == true) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppTheme.primaryRose,
            content: Text(
              '🎉 LEVEL UP! You reached Level ${res['new_level']}: ${res['new_title']}!',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
        );
      }
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(res['error'] ?? 'Failed to send message')),
      );
    }
  }

  Future<void> _refreshProfile() async {
    final updated = await ApiService.fetchProfile(widget.userId);
    if (updated != null && mounted) {
      setState(() => _profile = updated);
    }
  }

  Future<void> _toggleMode() async {
    final newMode = await ApiService.toggleMode(widget.userId);
    if (newMode != null && mounted) {
      _refreshProfile();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            newMode == 'normal'
                ? '🌸 Switched to Caring Best Friend Mode'
                : '🔥 Switched to Intimate Girlfriend Mode',
          ),
        ),
      );
    }
  }

  void _showMemoryBank() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => MemoryBankSheet(
        userId: widget.userId,
        onMemoriesCleared: _refreshProfile,
      ),
    );
  }

  void _showPaywall(String message) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => PaywallSheet(
        userId: widget.userId,
        paywallMessage: message,
      ),
    );
  }

  Future<void> _logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    if (mounted) {
      Navigator.of(context).pushReplacementNamed('/');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 0,
        title: Row(
          children: [
            Stack(
              children: [
                CircleAvatar(
                  radius: 20,
                  backgroundColor: AppTheme.primaryRose,
                  child: const Text('🌸', style: TextStyle(fontSize: 20)),
                ),
                Positioned(
                  right: 0,
                  bottom: 0,
                  child: Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                      color: Colors.greenAccent,
                      shape: BoxShape.circle,
                      border: Border.all(color: AppTheme.darkBg, width: 2),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _profile?.partnerName ?? 'Juhi',
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                Text(
                  _profile?.chatModeLabel ?? 'Caring Best Friend',
                  style: TextStyle(
                    fontSize: 11,
                    color: _profile?.chatMode == 'normal'
                        ? AppTheme.accentCyan
                        : AppTheme.primaryRose,
                  ),
                ),
              ],
            ),
          ],
        ),
        actions: [
          if (_profile != null)
            ModeTogglePill(
              chatMode: _profile!.chatMode,
              onToggle: _toggleMode,
            ),
          IconButton(
            icon: const Icon(Icons.psychology_outlined, color: AppTheme.accentCyan),
            tooltip: 'Memory Bank',
            onPressed: _showMemoryBank,
          ),
          IconButton(
            icon: const Icon(Icons.logout_rounded, color: Colors.white54),
            onPressed: _logout,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            if (_profile != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: XpBar(
                  level: _profile!.level,
                  title: _profile!.title,
                  percent: _profile!.percent,
                  xp: _profile!.xp,
                ),
              ),
            Expanded(
              child: _isLoading
                  ? const Center(
                      child: SpinKitPulse(color: AppTheme.primaryRose, size: 50),
                    )
                  : _messages.isEmpty
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: const [
                              Text('💬', style: TextStyle(fontSize: 40)),
                              SizedBox(height: 12),
                              Text(
                                'Say hello to Juhi!',
                                style: TextStyle(color: AppTheme.textLight, fontSize: 16),
                              ),
                            ],
                          ),
                        )
                      : ListView.builder(
                          controller: _scrollController,
                          itemCount: _messages.length,
                          itemBuilder: (context, index) {
                            final msg = _messages[index];
                            return ChatBubble(
                              message: msg,
                              onVisualizePressed: () {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('🎨 Type "/draw selfie in bedroom" to visualize photos!'),
                                  ),
                                );
                              },
                            );
                          },
                        ),
            ),
            if (_isSending)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                child: Row(
                  children: const [
                    SpinKitThreeBounce(color: AppTheme.primaryRose, size: 18),
                    SizedBox(width: 10),
                    Text(
                      'Juhi is typing...',
                      style: TextStyle(color: AppTheme.textLight, fontSize: 13, fontStyle: FontStyle.italic),
                    ),
                  ],
                ),
              ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              color: AppTheme.cardBg,
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _inputController,
                      style: const TextStyle(color: AppTheme.textWhite),
                      textCapitalization: TextCapitalization.sentences,
                      decoration: InputDecoration(
                        hintText: 'Message Juhi...',
                        hintStyle: const TextStyle(color: Colors.white38),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                          borderSide: BorderSide.none,
                        ),
                        filled: true,
                        fillColor: AppTheme.darkBg,
                        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                      ),
                      onSubmitted: (_) => _handleSend(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    decoration: const BoxDecoration(
                      color: AppTheme.primaryRose,
                      shape: BoxShape.circle,
                    ),
                    child: IconButton(
                      icon: const Icon(Icons.send_rounded, color: Colors.white, size: 20),
                      onPressed: _handleSend,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

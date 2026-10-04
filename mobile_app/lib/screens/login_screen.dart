import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import 'chat_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({Key? key}) : super(key: key);

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _idController = TextEditingController();
  final TextEditingController _nameController = TextEditingController();
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _checkExistingSession();
  }

  Future<void> _checkExistingSession() async {
    final prefs = await SharedPreferences.getInstance();
    final savedId = prefs.getInt('user_id');
    if (savedId != null && savedId > 0) {
      _navigateToChat(savedId);
    } else {
      // Default sample ID generator if first time
      final defaultId = 700000000 + (DateTime.now().millisecondsSinceEpoch % 999999);
      _idController.text = defaultId.toString();
      _nameController.text = 'User';
    }
  }

  Future<void> _login() async {
    final idText = _idController.text.trim();
    final nameText = _nameController.text.trim();

    if (idText.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a User ID or Telegram ID')),
      );
      return;
    }

    final userId = int.tryParse(idText);
    if (userId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('User ID must be numeric')),
      );
      return;
    }

    setState(() => _isLoading = true);

    final success = await ApiService.authUser(userId, nameText.toLowerCase(), nameText.isEmpty ? 'User' : nameText);

    setState(() => _isLoading = false);

    if (success) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt('user_id', userId);
      await prefs.setString('user_name', nameText);
      _navigateToChat(userId);
    } else {
      // Still navigate for offline/dry run readiness
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt('user_id', userId);
      _navigateToChat(userId);
    }
  }

  void _navigateToChat(int userId) {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => ChatScreen(userId: userId)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.darkBg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Icon(
                Icons.favorite_rounded,
                size: 64,
                color: AppTheme.primaryRose,
              ),
              const SizedBox(height: 16),
              const Text(
                'Karin AI Companion',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: AppTheme.textWhite,
                  fontSize: 26,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 6),
              const Text(
                'Synchronized Android App & Telegram Bot',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: AppTheme.accentCyan,
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 40),
              TextField(
                controller: _idController,
                keyboardType: TextInputType.number,
                style: const TextStyle(color: AppTheme.textWhite),
                decoration: InputDecoration(
                  labelText: 'Telegram ID / User ID',
                  labelStyle: const TextStyle(color: AppTheme.textLight),
                  filled: true,
                  fillColor: AppTheme.cardBg,
                  prefixIcon: const Icon(Icons.badge_outlined, color: AppTheme.accentCyan),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _nameController,
                style: const TextStyle(color: AppTheme.textWhite),
                decoration: InputDecoration(
                  labelText: 'Your Name (Nickname)',
                  labelStyle: const TextStyle(color: AppTheme.textLight),
                  filled: true,
                  fillColor: AppTheme.cardBg,
                  prefixIcon: const Icon(Icons.person_outline, color: AppTheme.primaryRose),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              const SizedBox(height: 24),
              SizedBox(
                height: 52,
                child: ElevatedButton(
                  onPressed: _isLoading ? null : _login,
                  child: _isLoading
                      ? const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                        )
                      : const Text(
                          'Start Chatting',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'Tip: Enter your Telegram User ID to sync your chat history, level, and memories between this app and your Telegram bot!',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white38, fontSize: 12, height: 1.3),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

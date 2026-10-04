import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';

class MemoryBankSheet extends StatefulWidget {
  final int userId;
  final VoidCallback onMemoriesCleared;

  const MemoryBankSheet({
    Key? key,
    required this.userId,
    required this.onMemoriesCleared,
  }) : super(key: key);

  @override
  State<MemoryBankSheet> createState() => _MemoryBankSheetState();
}

class _MemoryBankSheetState extends State<MemoryBankSheet> {
  List<String> _memories = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadMemories();
  }

  Future<void> _loadMemories() async {
    final list = await ApiService.fetchMemories(widget.userId);
    if (mounted) {
      setState(() {
        _memories = list;
        _isLoading = false;
      });
    }
  }

  Future<void> _clearMemories() async {
    final success = await ApiService.clearMemories(widget.userId);
    if (success && mounted) {
      setState(() {
        _memories.clear();
      });
      widget.onMemoriesCleared();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('🗑️ Memory bank cleared successfully!')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: MediaQuery.of(context).size.height * 0.65,
      padding: const EdgeInsets.all(20),
      decoration: const BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.only(
          topLeft: Radius.circular(24),
          topRight: Radius.circular(24),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: const [
                  Text('🧠', style: TextStyle(fontSize: 22)),
                  SizedBox(width: 8),
                  Text(
                    'Karin\'s Memory Bank',
                    style: TextStyle(
                      color: AppTheme.textWhite,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
              IconButton(
                icon: const Icon(Icons.close, color: AppTheme.textLight),
                onPressed: () => Navigator.pop(context),
              ),
            ],
          ),
          const SizedBox(height: 6),
          const Text(
            'Personal details, preferences, and feelings you\'ve shared that Karin remembers to care for you:',
            style: TextStyle(color: AppTheme.textLight, fontSize: 13),
          ),
          const Divider(color: Colors.white12, height: 24),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _memories.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: const [
                            Icon(Icons.psychology_outlined, size: 48, color: Colors.white24),
                            SizedBox(height: 12),
                            Text(
                              'No memories stored yet.\nChat with Karin and tell her about your day!',
                              textAlign: TextAlign.center,
                              style: TextStyle(color: Colors.white38, fontSize: 14),
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        itemCount: _memories.length,
                        itemBuilder: (context, index) {
                          return Container(
                            margin: const EdgeInsets.only(bottom: 8),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: AppTheme.darkBg,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: AppTheme.accentCyan.withOpacity(0.3)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.check_circle_outline, color: AppTheme.accentCyan, size: 18),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    _memories[index],
                                    style: const TextStyle(color: AppTheme.textWhite, fontSize: 14),
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
          ),
          if (_memories.isNotEmpty)
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.redAccent.withOpacity(0.2),
                  foregroundColor: Colors.redAccent,
                  side: const BorderSide(color: Colors.redAccent),
                ),
                onPressed: _clearMemories,
                icon: const Icon(Icons.delete_outline),
                label: const Text('Clear Memory Bank'),
              ),
            ),
        ],
      ),
    );
  }
}

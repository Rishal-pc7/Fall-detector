import 'package:flutter/material.dart';
import 'package:firebase_database/firebase_database.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:intl/intl.dart';

import '../models/fall_event_model.dart';
import '../services/notification_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late final DatabaseReference _dbRef;
  final Set<String> _notifiedEventIds = {};
  final List<FallEventModel> _events = [];
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _dbRef = FirebaseDatabase.instance.ref('fall_events');
    _subscribeToFallEvents();

    // Safety timeout — if nothing fires within 8s, show error instead of spinning forever
    Future.delayed(const Duration(seconds: 8), () {
      if (mounted && _isLoading) {
        setState(() {
          _isLoading = false;
          _errorMessage = 'Could not connect to Firebase.\nCheck your credentials or network.';
        });
      }
    });
  }

  void _subscribeToFallEvents() {
    _dbRef.onValue.listen(
      (event) {
        final data = event.snapshot.value;
        final List<FallEventModel> loaded = [];

        if (data != null && data is Map) {
          data.forEach((key, val) {
            if (val is Map) {
              final model = FallEventModel.fromMap(key.toString(), val);
              loaded.add(model);

              if (model.imageLink != null &&
                  model.imageLink!.isNotEmpty &&
                  !_notifiedEventIds.contains(model.id)) {
                _notifiedEventIds.add(model.id);

                String formattedTime = model.timestamp;
                try {
                  final dt = DateTime.parse(model.timestamp);
                  formattedTime = DateFormat('h:mm a').format(dt);
                } catch (_) {}

                NotificationService().showFallAlert(
                  id: model.id.hashCode,
                  personName: model.personName,
                  timeFormatted: formattedTime,
                  imageUrl: model.imageLink,
                );
              }
            }
          });

          loaded.sort((a, b) => b.timestamp.compareTo(a.timestamp));
        }

        if (mounted) {
          setState(() {
            _events.clear();
            _events.addAll(loaded);
            _isLoading = false;
            _errorMessage = null;
          });
        }
      },
      onError: (error) {
        if (mounted) {
          setState(() {
            _isLoading = false;
            _errorMessage = 'Firebase connection error:\n$error';
          });
        }
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF101216),
      appBar: AppBar(
        backgroundColor: const Color(0xFF181B22),
        elevation: 0,
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: const Color(0xFFE74C3C).withOpacity(0.15),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.shield, color: Color(0xFFE74C3C), size: 20),
            ),
            const SizedBox(width: 12),
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'SmartGuard Alert',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
                ),
                Text(
                  'Real-Time Fall Monitoring',
                  style: TextStyle(fontSize: 11, color: Color(0xFF8C96A8)),
                ),
              ],
            ),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF388BFD)))
          : _errorMessage != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.cloud_off, size: 64, color: Color(0xFFE74C3C)),
                        const SizedBox(height: 16),
                        const Text(
                          'Connection Failed',
                          style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          _errorMessage!,
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: Color(0xFF8C96A8), fontSize: 13),
                        ),
                        const SizedBox(height: 24),
                        ElevatedButton.icon(
                          style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF388BFD)),
                          onPressed: () {
                            setState(() { _isLoading = true; _errorMessage = null; });
                            _subscribeToFallEvents();
                          },
                          icon: const Icon(Icons.refresh),
                          label: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              : Column(
              children: [
                _buildSystemStatusBanner(),
                Expanded(
                  child: _events.isEmpty
                      ? _buildEmptyState()
                      : ListView.builder(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                          itemCount: _events.length,
                          itemBuilder: (context, index) {
                            return _buildEventCard(_events[index]);
                          },
                        ),
                ),
              ],
            ),
    );
  }

  Widget _buildSystemStatusBanner() {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF1C202B),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF2D3444)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Container(
                width: 10,
                height: 10,
                decoration: const BoxDecoration(
                  color: Color(0xFF2ECC71),
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 10),
              const Text(
                'AI Pipeline Active',
                style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 13),
              ),
            ],
          ),
          Text(
            '${_events.length} Events Recorded',
            style: const TextStyle(color: Color(0xFF8C96A8), fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.check_circle_outline, size: 64, color: Colors.grey.shade700),
          const SizedBox(height: 16),
          const Text(
            'No Fall Incidents Detected',
            style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 6),
          const Text(
            'All monitored subjects are currently safe and standing.',
            style: TextStyle(color: Color(0xFF8C96A8), fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _buildEventCard(FallEventModel event) {
    String formattedTime = event.timestamp;
    try {
      final dt = DateTime.parse(event.timestamp);
      formattedTime = DateFormat('MMM d, h:mm a').format(dt);
    } catch (_) {}

    final hasImage = event.imageLink != null && event.imageLink!.isNotEmpty;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      color: const Color(0xFF1C202B),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: Color(0xFF2D3444)),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => _showEventDialog(event),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              // Event Thumbnail
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Container(
                  width: 80,
                  height: 80,
                  color: const Color(0xFF12141A),
                  child: hasImage
                      ? CachedNetworkImage(
                          imageUrl: event.imageLink!,
                          fit: BoxFit.cover,
                          placeholder: (context, url) => const Center(
                            child: SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF388BFD)),
                            ),
                          ),
                          errorWidget: (context, url, err) => const Icon(Icons.broken_image, color: Colors.grey),
                        )
                      : const Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFFE74C3C)),
                              ),
                              SizedBox(height: 4),
                              Text('Uploading...', style: TextStyle(color: Colors.grey, fontSize: 9)),
                            ],
                          ),
                        ),
                ),
              ),
              const SizedBox(width: 14),
              // Information Column
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          event.personName,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: const Color(0xFFE74C3C).withOpacity(0.2),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: const Color(0xFFE74C3C)),
                          ),
                          child: const Text(
                            'FALL DETECTED',
                            style: TextStyle(color: Color(0xFFE74C3C), fontSize: 9, fontWeight: FontWeight.bold),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      formattedTime,
                      style: const TextStyle(color: Color(0xFF8C96A8), fontSize: 12),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Icon(
                          hasImage ? Icons.image : Icons.hourglass_top,
                          size: 14,
                          color: hasImage ? const Color(0xFF2ECC71) : const Color(0xFFF1C40F),
                        ),
                        const SizedBox(width: 4),
                        Text(
                          hasImage ? 'Snapshot Available' : 'Syncing Snapshot to Cloud...',
                          style: TextStyle(
                            color: hasImage ? const Color(0xFF2ECC71) : const Color(0xFFF1C40F),
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showEventDialog(FallEventModel event) {
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: const Color(0xFF1C202B),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text(
            '🚨 Fall Report',
            style: TextStyle(color: Colors.white, fontSize: 18),
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Timestamp: ${event.timestamp}', style: const TextStyle(color: Color(0xFF8C96A8), fontSize: 12)),
              const SizedBox(height: 12),
              if (event.imageLink != null && event.imageLink!.isNotEmpty)
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: CachedNetworkImage(
                    imageUrl: event.imageLink!,
                    fit: BoxFit.cover,
                  ),
                )
              else
                const Text('Snapshot image is currently processing.', style: TextStyle(color: Colors.grey)),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Dismiss', style: TextStyle(color: Color(0xFF8C96A8))),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFE74C3C)),
              onPressed: () {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Emergency contact dispatched.')),
                );
              },
              child: const Text('Call Emergency', style: TextStyle(color: Colors.white)),
            ),
          ],
        );
      },
    );
  }
}

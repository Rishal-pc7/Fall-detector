class FallEventModel {
  final String id;
  final String personName;
  final String timestamp;
  final String? imageLink;

  FallEventModel({
    required this.id,
    required this.personName,
    required this.timestamp,
    this.imageLink,
  });

    return FallEventModel(
      id: id,
      personName: map['person_name']?.toString() ?? 'Fall detected',
      timestamp: map['timestamp']?.toString() ?? '',
      imageLink: map['image_link']?.toString(),
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'timestamp': timestamp,
      'image_link': imageLink,
    };
  }
}

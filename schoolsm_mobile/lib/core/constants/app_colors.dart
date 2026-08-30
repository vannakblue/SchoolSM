import 'package:flutter/material.dart';

class AppColors {
  // Primary Palette
  static const Color primary = Color(0xFF4F46E5);       // Indigo 600
  static const Color primaryDark = Color(0xFF3730A3);   // Indigo 800
  static const Color primaryLight = Color(0xFF818CF8);  // Indigo 400
  static const Color secondary = Color(0xFF06B6D4);     // Cyan 500
  static const Color accent = Color(0xFFF59E0B);        // Amber 500

  // Semantic Status Colors
  static const Color success = Color(0xFF10B981);       // Emerald 500
  static const Color warning = Color(0xFFF59E0B);       // Amber 500
  static const Color danger = Color(0xFFEF4444);        // Rose 500
  static const Color info = Color(0xFF3B82F6);          // Blue 500

  // Background & Surfaces
  static const Color bgDark = Color(0xFF0F172A);        // Slate 900
  static const Color bgDarkCard = Color(0xFF1E293B);    // Slate 800
  static const Color bgDarkCardAlt = Color(0xFF334155); // Slate 700
  static const Color bgLight = Color(0xFFF8FAFC);       // Slate 50
  static const Color bgLightCard = Color(0xFFFFFFFF);
  static const Color borderLight = Color(0xFFE2E8F0);
  static const Color borderDark = Color(0xFF334155);

  // Text Colors
  static const Color textPrimary = Color(0xFF0F172A);
  static const Color textSecondary = Color(0xFF64748B);
  static const Color textDarkPrimary = Color(0xFFF8FAFC);
  static const Color textDarkSecondary = Color(0xFF94A3B8);

  // Gradients
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [Color(0xFF4F46E5), Color(0xFF06B6D4)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient cardGradient = LinearGradient(
    colors: [Color(0xFF1E293B), Color(0xFF0F172A)],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );

  static const LinearGradient goldGradient = LinearGradient(
    colors: [Color(0xFFF59E0B), Color(0xFFD97706)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}

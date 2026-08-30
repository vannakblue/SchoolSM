import 'dart:io';
import 'package:flutter/material.dart';
import 'package:qr_code_scanner/qr_code_scanner.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/api_constants.dart';
import '../../../core/api/api_client.dart';

class QRScannerScreen extends StatefulWidget {
  const QRScannerScreen({super.key});

  @override
  State<QRScannerScreen> createState() => _QRScannerScreenState();
}

class _QRScannerScreenState extends State<QRScannerScreen> {
  final GlobalKey qrKey = GlobalKey(debugLabel: 'QR');
  QRViewController? controller;
  bool _isProcessing = false;

  // In order to get hot reload to work we need to pause the camera if the platform
  // is android, or resume the camera if the platform is iOS.
  @override
  void reassemble() {
    super.reassemble();
    if (Platform.isAndroid) {
      controller?.pauseCamera();
    }
    controller?.resumeCamera();
  }

  @override
  void dispose() {
    controller?.dispose();
    super.dispose();
  }

  void _onQRViewCreated(QRViewController controller) {
    setState(() {
      this.controller = controller;
    });
    controller.scannedDataStream.listen((scanData) async {
      if (_isProcessing) return;
      final code = scanData.code;
      if (code != null && code.isNotEmpty) {
        setState(() => _isProcessing = true);
        controller.pauseCamera();
        await _processScan(code);
      }
    });
  }

  Future<void> _processScan(String code) async {
    try {
      final res = await ApiClient().dio.post(
        ApiConstants.qrScan,
        data: {
          'qr_code': code.trim(),
          'scan_type': 'AUTO',
        },
      );

      final data = res.data;
      if (!mounted) return;

      _showResultDialog(
        isSuccess: true,
        title: data['type'] == 'TEACHER' ? "វត្តមានគ្រូបង្រៀន" : "វត្តមានសិស្ស",
        message: data['message'] ?? 'កត់ត្រាវត្តមានជោគជ័យ!',
        name: data['name'] ?? '',
        id: data['id'] ?? '',
        time: data['time'] ?? '',
      );
    } catch (e) {
      if (!mounted) return;
      _showResultDialog(
        isSuccess: false,
        title: "ស្កេនមិនជោគជ័យ",
        message: ApiClient.getErrorMessage(e),
        name: code,
        id: '',
        time: '',
      );
    }
  }

  void _showResultDialog({
    required bool isSuccess,
    required String title,
    required String message,
    required String name,
    required String id,
    required String time,
  }) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        contentPadding: const EdgeInsets.all(24),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isSuccess ? AppColors.success.withValues(alpha: 0.15) : AppColors.danger.withValues(alpha: 0.15),
              ),
              child: Icon(
                isSuccess ? Icons.check_circle_rounded : Icons.error_outline_rounded,
                size: 48,
                color: isSuccess ? AppColors.success : AppColors.danger,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              title,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              message,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                color: isSuccess ? AppColors.textPrimary : AppColors.danger,
              ),
            ),
            if (name.isNotEmpty) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.bgLight,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(name, style: const TextStyle(fontWeight: FontWeight.bold)),
                    if (time.isNotEmpty)
                      Text("ម៉ោង: $time", style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                  ],
                ),
              ),
            ],
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 46,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: isSuccess ? AppColors.primary : AppColors.bgDark,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: () {
                  Navigator.pop(ctx);
                  setState(() => _isProcessing = false);
                  controller?.resumeCamera();
                },
                child: const Text("ស្កេនបន្ត (Next Scan)", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showManualEntryDialog() {
    final codeController = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text("វាយបញ្ចូលកូដដោយផ្ទាល់", style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        content: TextField(
          controller: codeController,
          autofocus: true,
          decoration: InputDecoration(
            hintText: "ឧទាហរណ៍: STU-2026-0001 ឬ Teacher ID",
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text("បោះបង់")),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.primary),
            onPressed: () {
              final code = codeController.text.trim();
              if (code.isNotEmpty) {
                Navigator.pop(ctx);
                _processScan(code);
              }
            },
            child: const Text("បញ្ជូន", style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final scanArea = (MediaQuery.of(context).size.width < 400 ||
            MediaQuery.of(context).size.height < 400)
        ? 220.0
        : 260.0;

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        elevation: 0,
        title: const Text("ម៉ាស៊ីនស្កេន QR វត្តមាន", style: TextStyle(color: Colors.white, fontSize: 18)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.flash_on, color: Colors.white),
            onPressed: () async {
              await controller?.toggleFlash();
            },
          ),
          IconButton(
            icon: const Icon(Icons.flip_camera_ios, color: Colors.white),
            onPressed: () async {
              await controller?.flipCamera();
            },
          ),
          IconButton(
            icon: const Icon(Icons.keyboard, color: Colors.white),
            tooltip: "វាយបញ្ចូលកូដ",
            onPressed: _showManualEntryDialog,
          ),
        ],
      ),
      body: Stack(
        alignment: Alignment.center,
        children: [
          QRView(
            key: qrKey,
            onQRViewCreated: _onQRViewCreated,
            overlay: QrScannerOverlayShape(
              borderColor: AppColors.secondary,
              borderRadius: 20,
              borderLength: 30,
              borderWidth: 6,
              cutOutSize: scanArea,
            ),
          ),
          Positioned(
            bottom: 40,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.7),
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Text(
                "តម្រង់កាមេរ៉ាទៅលើ QR Code របស់សិស្ស ឬគ្រូ",
                style: TextStyle(color: Colors.white, fontSize: 13),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

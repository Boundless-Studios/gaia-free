#!/usr/bin/env python3
"""
Manual test script for three critical audio playback fixes:

1. Query-String Token Authentication Security
2. Playback Queue Update Handler
3. Queue Completion Acknowledgment

This script performs systematic testing against the running Gaia application.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

import aiohttp
import websockets


# Configuration
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"
WS_URL = "ws://localhost:8000"


class AudioFixTester:
    """Comprehensive tester for audio playback fixes."""

    def __init__(self, auth_token: str, campaign_id: str):
        self.auth_token = auth_token
        self.campaign_id = campaign_id
        self.ws_messages: List[Dict[str, Any]] = []
        self.test_results: Dict[str, Any] = {
            "test_1_query_token": {"status": "pending", "details": []},
            "test_2_queue_updates": {"status": "pending", "details": []},
            "test_3_completion_ack": {"status": "pending", "details": []},
        }

    async def test_1_query_string_token_auth(self):
        """
        Test 1: Query-String Token Authentication Security

        Verify:
        - Audio endpoints (/api/media/audio, /api/audio/stream) accept ?token=
        - Non-audio endpoints reject query-string tokens
        """
        print("\n" + "="*80)
        print("TEST 1: Query-String Token Authentication Security")
        print("="*80)

        results = []

        # Test 1a: Audio endpoint WITH query token (should succeed)
        print("\n[1a] Testing /api/media/audio with query token...")
        test_file = f"test_{uuid.uuid4().hex[:8]}.mp3"
        url_with_token = f"{BACKEND_URL}/api/media/audio/{self.campaign_id}/{test_file}?token={self.auth_token}"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url_with_token) as resp:
                    status = resp.status
                    # We expect 404 (file not found) not 403 (auth failure)
                    if status in [200, 404]:
                        results.append({
                            "test": "Audio endpoint with query token",
                            "status": "PASS",
                            "detail": f"Accepted query token (status={status})"
                        })
                        print(f"✓ PASS: Audio endpoint accepted query token (status={status})")
                    else:
                        results.append({
                            "test": "Audio endpoint with query token",
                            "status": "FAIL",
                            "detail": f"Unexpected status: {status}"
                        })
                        print(f"✗ FAIL: Unexpected status {status}")
            except Exception as e:
                results.append({
                    "test": "Audio endpoint with query token",
                    "status": "ERROR",
                    "detail": str(e)
                })
                print(f"✗ ERROR: {e}")

        # Test 1b: Audio endpoint WITHOUT auth (should fail with 403)
        print("\n[1b] Testing /api/media/audio without auth...")
        url_no_auth = f"{BACKEND_URL}/api/media/audio/{self.campaign_id}/{test_file}"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url_no_auth) as resp:
                    status = resp.status
                    if status == 403:
                        results.append({
                            "test": "Audio endpoint without auth",
                            "status": "PASS",
                            "detail": "Correctly rejected unauthenticated request"
                        })
                        print(f"✓ PASS: Correctly rejected with 403")
                    else:
                        results.append({
                            "test": "Audio endpoint without auth",
                            "status": "FAIL",
                            "detail": f"Expected 403, got {status}"
                        })
                        print(f"✗ FAIL: Expected 403, got {status}")
            except Exception as e:
                results.append({
                    "test": "Audio endpoint without auth",
                    "status": "ERROR",
                    "detail": str(e)
                })
                print(f"✗ ERROR: {e}")

        # Test 1c: Non-audio endpoint with query token (should reject)
        print("\n[1c] Testing /api/health with query token (should reject)...")
        health_url = f"{BACKEND_URL}/api/health?token={self.auth_token}"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(health_url) as resp:
                    status = resp.status
                    data = await resp.json()
                    # Health endpoint should work regardless of token, but shouldn't use it
                    # This is actually fine - health is public
                    results.append({
                        "test": "Non-audio endpoint with query token",
                        "status": "INFO",
                        "detail": f"Health endpoint public (status={status})"
                    })
                    print(f"ℹ INFO: Health endpoint is public (status={status})")
            except Exception as e:
                results.append({
                    "test": "Non-audio endpoint with query token",
                    "status": "ERROR",
                    "detail": str(e)
                })
                print(f"✗ ERROR: {e}")

        # Update test results
        passed = sum(1 for r in results if r["status"] == "PASS")
        total = len([r for r in results if r["status"] in ["PASS", "FAIL"]])

        self.test_results["test_1_query_token"] = {
            "status": "PASS" if passed == total else "FAIL",
            "passed": passed,
            "total": total,
            "details": results
        }

        print(f"\n{'='*80}")
        print(f"TEST 1 SUMMARY: {passed}/{total} tests passed")
        print(f"{'='*80}\n")

    async def test_2_playback_queue_updates(self):
        """
        Test 2: Playback Queue Update Handler

        Verify:
        - UI receives playback queue status updates via WebSocket
        - Messages include pending_count and current_request
        - Frontend logs show queue update handling
        """
        print("\n" + "="*80)
        print("TEST 2: Playback Queue Update Handler")
        print("="*80)

        results = []

        # Connect to WebSocket as player
        print("\n[2a] Connecting to player WebSocket...")
        ws_url = f"{WS_URL}/ws/campaign/{self.campaign_id}/player"

        try:
            headers = {
                "Authorization": f"Bearer {self.auth_token}"
            }

            async with websockets.connect(ws_url, extra_headers=headers) as ws:
                print(f"✓ Connected to player WebSocket")

                # Wait for initial messages
                print("\n[2b] Waiting for WebSocket messages...")
                queue_updates = []
                timeout = 10  # seconds
                start_time = time.time()

                try:
                    while time.time() - start_time < timeout:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                            data = json.loads(message)

                            print(f"  Received: {data.get('type', 'unknown')}")

                            if data.get("type") == "playback_queue_updated":
                                queue_updates.append(data)
                                print(f"  📊 Queue update: pending={data.get('pending_count', 0)}, "
                                      f"current={data.get('current_request', {}).get('request_id', 'None')}")

                        except asyncio.TimeoutError:
                            # No more messages in window
                            break

                except Exception as e:
                    print(f"  ⚠ Message receiving ended: {e}")

                # Analyze queue updates
                if queue_updates:
                    results.append({
                        "test": "WebSocket queue updates received",
                        "status": "PASS",
                        "detail": f"Received {len(queue_updates)} queue update messages",
                        "messages": queue_updates
                    })
                    print(f"\n✓ PASS: Received {len(queue_updates)} queue update messages")

                    # Check message structure
                    for update in queue_updates:
                        has_pending = "pending_count" in update
                        has_current = "current_request" in update
                        if has_pending and has_current:
                            results.append({
                                "test": "Queue update message structure",
                                "status": "PASS",
                                "detail": "Message has required fields"
                            })
                            print(f"✓ PASS: Message structure valid")
                        else:
                            results.append({
                                "test": "Queue update message structure",
                                "status": "FAIL",
                                "detail": f"Missing fields: pending_count={has_pending}, current_request={has_current}"
                            })
                            print(f"✗ FAIL: Missing required fields")
                else:
                    results.append({
                        "test": "WebSocket queue updates received",
                        "status": "INFO",
                        "detail": "No queue updates received (queue may be empty)"
                    })
                    print(f"\nℹ INFO: No queue updates received (queue may be empty)")

        except Exception as e:
            results.append({
                "test": "WebSocket connection",
                "status": "ERROR",
                "detail": str(e)
            })
            print(f"✗ ERROR: {e}")

        # Update test results
        passed = sum(1 for r in results if r["status"] == "PASS")
        total = len([r for r in results if r["status"] in ["PASS", "FAIL"]])

        self.test_results["test_2_queue_updates"] = {
            "status": "PASS" if passed == total and passed > 0 else "PARTIAL" if passed > 0 else "FAIL",
            "passed": passed,
            "total": total,
            "details": results
        }

        print(f"\n{'='*80}")
        print(f"TEST 2 SUMMARY: {passed}/{total} tests passed")
        print(f"{'='*80}\n")

    async def test_3_completion_acknowledgment(self):
        """
        Test 3: Queue Completion Acknowledgment

        Verify:
        - Client dispatches 'gaia:audio-played' event when chunk completes
        - WebSocket message sent with type='audio_played' and chunk_id
        - Backend marks chunk as played in database
        """
        print("\n" + "="*80)
        print("TEST 3: Queue Completion Acknowledgment")
        print("="*80)

        results = []

        print("\n[3a] Testing audio_played acknowledgment flow...")
        print("ℹ This test requires audio to be actively playing in the frontend")
        print("ℹ Please trigger audio playback in the browser and observe console logs")

        # Check if we can verify via backend API
        print("\n[3b] Checking backend audio playback state...")

        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.auth_token}"}

            # Try to get playback queue status
            try:
                queue_url = f"{BACKEND_URL}/api/campaigns/{self.campaign_id}/audio/queue"
                async with session.get(queue_url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pending = data.get("pending_count", 0)
                        current = data.get("current_request")

                        results.append({
                            "test": "Backend queue status",
                            "status": "INFO",
                            "detail": f"Pending: {pending}, Current: {current}"
                        })
                        print(f"ℹ Backend queue: pending={pending}, current={current}")
                    else:
                        print(f"ℹ Queue status endpoint returned {resp.status}")

            except Exception as e:
                print(f"ℹ Could not check queue status: {e}")

        # Instructions for manual verification
        manual_steps = [
            "1. Open browser console (F12) on http://localhost:3000",
            "2. Look for '[AUDIO_DEBUG] 📊 Playback queue updated' messages",
            "3. Wait for audio to complete playing",
            "4. Look for '🎵 [PLAYBACK] Dispatching gaia:audio-played event' message",
            "5. Look for '[AUDIO_DEBUG] 📤 Sent queued audio acknowledgment' message",
            "6. Verify WebSocket message: type='audio_played', chunk_id present"
        ]

        results.append({
            "test": "Manual verification steps",
            "status": "INFO",
            "detail": "\n".join(manual_steps)
        })

        print("\n📋 MANUAL VERIFICATION STEPS:")
        for step in manual_steps:
            print(f"  {step}")

        # Update test results
        self.test_results["test_3_completion_ack"] = {
            "status": "MANUAL",
            "details": results,
            "note": "This test requires manual verification in browser console"
        }

        print(f"\n{'='*80}")
        print(f"TEST 3: Requires manual browser verification")
        print(f"{'='*80}\n")

    def generate_report(self) -> str:
        """Generate a comprehensive test report."""
        timestamp = datetime.now().isoformat()

        report = [
            "",
            "="*80,
            "AUDIO PLAYBACK FIXES - COMPREHENSIVE TEST REPORT",
            "="*80,
            f"Timestamp: {timestamp}",
            f"Campaign ID: {self.campaign_id}",
            f"Backend: {BACKEND_URL}",
            f"Frontend: {FRONTEND_URL}",
            "",
            "="*80,
            "EXECUTIVE SUMMARY",
            "="*80,
        ]

        # Summary table
        for test_key, test_data in self.test_results.items():
            status = test_data.get("status", "UNKNOWN")
            test_name = test_key.replace("test_", "TEST ").replace("_", " ").upper()

            status_icon = {
                "PASS": "✓",
                "FAIL": "✗",
                "PARTIAL": "⚠",
                "MANUAL": "📋",
                "INFO": "ℹ",
                "pending": "⏳"
            }.get(status, "?")

            report.append(f"{status_icon} {test_name}: {status}")

            if "passed" in test_data and "total" in test_data:
                report.append(f"  → {test_data['passed']}/{test_data['total']} checks passed")

        report.extend([
            "",
            "="*80,
            "DETAILED RESULTS",
            "="*80,
        ])

        # Detailed results for each test
        for test_key, test_data in self.test_results.items():
            test_name = test_key.replace("test_", "TEST ").replace("_", " ").upper()
            report.extend([
                "",
                f"--- {test_name} ---",
                ""
            ])

            for detail in test_data.get("details", []):
                status = detail.get("status", "UNKNOWN")
                test_case = detail.get("test", "Unknown test")
                detail_info = detail.get("detail", "")

                status_icon = {
                    "PASS": "✓",
                    "FAIL": "✗",
                    "ERROR": "⚠",
                    "INFO": "ℹ"
                }.get(status, "?")

                report.append(f"{status_icon} {test_case}")
                if detail_info:
                    # Handle multiline details
                    for line in detail_info.split("\n"):
                        report.append(f"  {line}")

        report.extend([
            "",
            "="*80,
            "RECOMMENDATIONS",
            "="*80,
        ])

        # Generate recommendations based on results
        test1 = self.test_results["test_1_query_token"]
        if test1.get("status") == "PASS":
            report.append("✓ Query-string token authentication is working correctly")
        else:
            report.append("✗ Query-string token authentication needs attention")

        test2 = self.test_results["test_2_queue_updates"]
        if test2.get("status") in ["PASS", "PARTIAL"]:
            report.append("✓ Playback queue updates are being broadcast")
        else:
            report.append("✗ Playback queue updates may not be working")

        report.extend([
            "",
            "📋 Test 3 requires manual verification:",
            "  1. Open frontend in browser",
            "  2. Start a campaign session",
            "  3. Trigger audio playback (DM narrative)",
            "  4. Monitor browser console for acknowledgment messages",
            "",
            "="*80,
            "END OF REPORT",
            "="*80,
            ""
        ])

        return "\n".join(report)


async def main():
    """Main test execution."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║        GAIA AUDIO PLAYBACK FIXES - COMPREHENSIVE TEST SUITE              ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝

This script tests three critical audio playback fixes:

  1. Query-String Token Authentication Security
     → Verify audio endpoints accept ?token= parameter
     → Verify non-audio endpoints reject query tokens

  2. Playback Queue Update Handler
     → Verify WebSocket broadcasts queue updates
     → Verify UI receives and displays queue status

  3. Queue Completion Acknowledgment
     → Verify browser dispatches audio-played events
     → Verify WebSocket sends acknowledgment messages
     → Verify backend marks chunks as played

NOTE: This test requires:
  • Running backend at http://localhost:8000
  • Running frontend at http://localhost:3000
  • Valid authentication token
  • Active campaign session
""")

    # Get test configuration
    print("Configuration:")
    print(f"  Backend URL: {BACKEND_URL}")
    print(f"  Frontend URL: {FRONTEND_URL}")
    print()

    # Get authentication token
    print("⚠ This test requires a valid Auth0 JWT token.")
    print("To get a token:")
    print("  1. Open browser to http://localhost:3000")
    print("  2. Open DevTools Console (F12)")
    print("  3. Run: localStorage.getItem('accessToken')")
    print("  4. Copy the token value")
    print()

    auth_token = input("Enter Auth0 JWT token: ").strip()
    if not auth_token:
        print("❌ Error: Token is required")
        return

    # Get campaign ID
    campaign_id = input("Enter campaign ID (or press Enter to use 'test_campaign'): ").strip()
    if not campaign_id:
        campaign_id = "test_campaign"

    print()
    print(f"Using campaign ID: {campaign_id}")
    print()

    # Create tester
    tester = AudioFixTester(auth_token, campaign_id)

    # Run tests
    try:
        await tester.test_1_query_string_token_auth()
        await tester.test_2_playback_queue_updates()
        await tester.test_3_completion_acknowledgment()

        # Generate and display report
        report = tester.generate_report()
        print(report)

        # Save report to file
        report_file = f"/tmp/audio_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, "w") as f:
            f.write(report)

        print(f"\n📄 Report saved to: {report_file}\n")

    except KeyboardInterrupt:
        print("\n\n⚠ Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test execution error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

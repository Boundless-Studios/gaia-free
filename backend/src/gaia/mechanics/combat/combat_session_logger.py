"""Combat logging system for debugging and analysis."""
import json
import logging
import time
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from gaia.mechanics.combat.combat_event_log import (
    CombatEventLog, DiceRollLog, CombatPerformanceMetrics
)
from gaia.mechanics.combat.combat_json_encoder import CombatJSONEncoder
from gaia.models.combat import CombatSession

logger = logging.getLogger(__name__)


class CombatLogger:
    """Specialized logger for combat system debugging and analysis."""

    def __init__(self, campaign_manager=None):
        """Initialize the combat logger.

        Args:
            campaign_manager: Campaign manager for accessing storage paths
        """
        self.campaign_manager = campaign_manager
        self.active_logs: Dict[str, List[CombatEventLog]] = {}
        self.metrics: Dict[str, CombatPerformanceMetrics] = {}

    def get_combat_log_path(self, campaign_id: str, session_id: str,
                           active: bool = True) -> Optional[Path]:
        """Get the path for combat log files.

        Args:
            campaign_id: Campaign identifier
            session_id: Combat session identifier
            active: Whether this is active combat or history

        Returns:
            Path to combat log directory
        """
        if not self.campaign_manager:
            return None

        data_path = self.campaign_manager.get_campaign_data_path(campaign_id)
        if not data_path:
            return None

        if active:
            log_path = data_path / "combat" / "active"
        else:
            # Use timestamp in history folder name
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            log_path = data_path / "combat" / "history" / f"combat_{timestamp}"

        log_path.mkdir(parents=True, exist_ok=True)
        return log_path

    def log_user_input(self, session_id: str, campaign_id: str,
                      user_input: str, context: Dict[str, Any]) -> None:
        """Log raw user input with context.

        Args:
            session_id: Combat session ID
            campaign_id: Campaign ID
            user_input: Raw user command
            context: Additional context
        """
        event = CombatEventLog(
            event_type="user_input",
            user_input=user_input,
            context_provided=context,
            state_before=self._snapshot_state(session_id)
        )

        self._write_event(campaign_id, session_id, event)
        logger.debug(f"Logged user input for combat {session_id}: {user_input[:50]}...")

    def log_agent_request(self, session_id: str, campaign_id: str,
                         agent_name: str, model: str,
                         context: Optional[Dict[str, Any]] = None) -> str:
        """Log request sent to agent.

        Args:
            session_id: Combat session ID
            campaign_id: Campaign ID
            agent_name: Name of the agent
            prompt: Full prompt sent to agent
            model: Model being used

        Returns:
            Event ID for tracking
        """
        event = CombatEventLog(
            event_type="agent_request",
            agent_name=agent_name,
            model_used=model,
            state_before=self._snapshot_state(session_id),
            context_provided=context or {}
        )

        self._write_event(campaign_id, session_id, event)
        logger.debug(f"Logged agent request to {agent_name} using {model}")
        return event.event_id

    def log_agent_response(self, session_id: str, campaign_id: str,
                          event_id: str, agent_name: str,
                          response: Dict, time_ms: int) -> None:
        """Log complete agent response.

        Args:
            session_id: Combat session ID
            campaign_id: Campaign ID
            event_id: Event ID from request
            agent_name: Name of the agent
            response: Full agent response
            time_ms: Processing time in milliseconds
        """
        event = CombatEventLog(
            event_id=event_id,  # Use same ID to link request/response
            event_type="agent_response",
            agent_name=agent_name,
            agent_response=response,
            processing_time_ms=time_ms,
            state_after=self._snapshot_state(session_id)
        )

        # Calculate state changes
        if event.state_before and event.state_after:
            event.state_changes = self._calculate_state_changes(
                event.state_before, event.state_after
            )

        self._write_event(campaign_id, session_id, event)
        self._update_metrics(session_id, event)
        logger.debug(f"Logged agent response from {agent_name} ({time_ms}ms)")

    def log_dice_roll(self, session_id: str, campaign_id: str,
                     roll_type: str, expression: str,
                     result: Dict[str, Any]) -> None:
        """Log dice roll details.

        Args:
            session_id: Combat session ID
            campaign_id: Campaign ID
            roll_type: Type of roll (attack, damage, etc)
            expression: Dice expression
            result: Roll result
        """
        dice_log = DiceRollLog(
            roll_type=roll_type,
            expression=expression,
            rolls=result.get("rolls", []),
            modifier=result.get("modifier", 0),
            total=result.get("total", 0),
            critical=result.get("critical", False),
            fumble=result.get("fumble", False),
            advantage=result.get("advantage", False),
            disadvantage=result.get("disadvantage", False),
            context=result.get("context", {})
        )

        event = CombatEventLog(
            event_type="dice_roll",
            dice_rolls=[dice_log.to_dict()]
        )

        self._write_event(campaign_id, session_id, event)
        logger.debug(f"Logged {roll_type} roll: {expression} = {result.get('total')}")

    def log_validation_failure(self, session_id: str, campaign_id: str,
                              action: str, reason: str,
                              context: Dict[str, Any] = None) -> None:
        """Log why an action was rejected.

        Args:
            session_id: Combat session ID
            campaign_id: Campaign ID
            action: Action that failed
            reason: Why it failed
            context: Additional context
        """
        event = CombatEventLog(
            event_type="validation_failure",
            validation_results=[{
                "action": action,
                "valid": False,
                "reason": reason,
                "context": context or {}
            }],
            warnings=[f"Action '{action}' failed validation: {reason}"]
        )

        self._write_event(campaign_id, session_id, event)
        logger.warning(f"Validation failed for {action}: {reason}")

    def log_state_transition(self, session_id: str, campaign_id: str,
                            before: Dict, after: Dict,
                            action_name: str = None) -> None:
        """Log state changes.

        Args:
            session_id: Combat session ID
            campaign_id: Campaign ID
            before: State before change
            after: State after change
            action_name: Action that caused the change
        """
        changes = self._calculate_state_changes(before, after)

        event = CombatEventLog(
            event_type="state_transition",
            state_before=before,
            state_after=after,
            state_changes=changes,
            context_provided={"action": action_name} if action_name else {}
        )

        self._write_event(campaign_id, session_id, event)
        logger.debug(f"State transition logged: {len(changes)} changes")

    def log_error(self, session_id: str, campaign_id: str,
                 error_msg: str, stack_trace: str = None,
                 context: Dict[str, Any] = None) -> None:
        """Log an error with full context.

        Args:
            session_id: Combat session ID
            campaign_id: Campaign ID
            error_msg: Error message
            stack_trace: Full stack trace
            context: Additional context
        """
        event = CombatEventLog(
            event_type="error",
            errors=[error_msg],
            context_provided=context or {},
            state_before=self._snapshot_state(session_id)
        )

        if stack_trace:
            event.errors.append(f"Stack trace:\n{stack_trace}")

        self._write_event(campaign_id, session_id, event)
        logger.error(f"Combat error in {session_id}: {error_msg}")

    def log_action_result(self, session_id: str, campaign_id: str,
                         action: Dict[str, Any], time_ms: int) -> None:
        """Log the result of a combat action.

        Args:
            session_id: Combat session ID
            campaign_id: Campaign ID
            action: Action that was executed
            time_ms: Processing time
        """
        event = CombatEventLog(
            event_type="action_result",
            parsed_actions=[action],
            processing_time_ms=time_ms,
            state_after=self._snapshot_state(session_id)
        )

        self._write_event(campaign_id, session_id, event)
        self._update_metrics(session_id, event)
        logger.debug(f"Action result logged: {action.get('action_type')}")

    def _write_event(self, campaign_id: str, session_id: str,
                    event: CombatEventLog) -> None:
        """Write event to JSONL log file.

        Args:
            campaign_id: Campaign ID
            session_id: Combat session ID
            event: Event to log
        """
        # Store in memory
        if session_id not in self.active_logs:
            self.active_logs[session_id] = []
        self.active_logs[session_id].append(event)

        # Write to disk if campaign manager available
        if self.campaign_manager:
            log_path = self.get_combat_log_path(campaign_id, session_id, active=True)
            if log_path:
                log_file = log_path / "event_log.jsonl"
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event.to_dict(), ensure_ascii=False, cls=CombatJSONEncoder) + "\n")

    def _snapshot_state(self, session_id: str) -> Dict[str, Any]:
        """Take a snapshot of current combat state.

        Args:
            session_id: Combat session ID

        Returns:
            State snapshot
        """
        # This would get the actual combat state from state manager
        # For now, return placeholder
        return {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            # Would include combatant states, round number, etc.
        }

    def _calculate_state_changes(self, before: Dict, after: Dict) -> Dict[str, Any]:
        """Calculate the differences between two states.

        Args:
            before: State before
            after: State after

        Returns:
            Dictionary of changes
        """
        changes = {}

        # Find changed values
        for key in after:
            if key not in before:
                changes[key] = {"added": after[key]}
            elif before[key] != after[key]:
                changes[key] = {
                    "before": before[key],
                    "after": after[key]
                }

        # Find removed values
        for key in before:
            if key not in after:
                changes[key] = {"removed": before[key]}

        return changes

    def _update_metrics(self, session_id: str, event: CombatEventLog) -> None:
        """Update performance metrics based on event.

        Args:
            session_id: Combat session ID
            event: Event to process
        """
        if session_id not in self.metrics:
            self.metrics[session_id] = CombatPerformanceMetrics(session_id=session_id)

        metrics = self.metrics[session_id]
        metrics.total_events += 1

        if event.event_type == "action_result":
            metrics.total_actions += 1

        if event.dice_rolls:
            metrics.total_dice_rolls += len(event.dice_rolls)

        if event.errors:
            metrics.total_errors += len(event.errors)

        if event.warnings:
            metrics.total_warnings += len(event.warnings)

        if event.processing_time_ms:
            # Update timing metrics
            if metrics.avg_response_time_ms == 0:
                metrics.avg_response_time_ms = event.processing_time_ms
            else:
                metrics.avg_response_time_ms = (
                    (metrics.avg_response_time_ms * (metrics.total_events - 1) +
                     event.processing_time_ms) / metrics.total_events
                )

            metrics.max_response_time_ms = max(
                metrics.max_response_time_ms, event.processing_time_ms
            )
            metrics.min_response_time_ms = min(
                metrics.min_response_time_ms or float('inf'),
                event.processing_time_ms
            )
            metrics.total_processing_time_ms += event.processing_time_ms

    def finalize_session(self, session_id: str, campaign_id: str) -> None:
        """Finalize a combat session, moving logs to history.

        Args:
            session_id: Combat session ID
            campaign_id: Campaign ID
        """
        if not self.campaign_manager:
            return

        # Get paths
        active_path = self.get_combat_log_path(campaign_id, session_id, active=True)
        history_path = self.get_combat_log_path(campaign_id, session_id, active=False)

        if active_path and history_path:
            # Move active logs to history
            import shutil
            for file in active_path.glob("*"):
                shutil.move(str(file), str(history_path / file.name))

            # Save metrics
            if session_id in self.metrics:
                metrics_file = history_path / "metrics.json"
                with open(metrics_file, "w", encoding="utf-8") as f:
                    json.dump(self.metrics[session_id].to_dict(), f, indent=2)

            # Generate debug report
            self._generate_debug_report(session_id, history_path)

        # Clean up memory
        if session_id in self.active_logs:
            del self.active_logs[session_id]
        if session_id in self.metrics:
            del self.metrics[session_id]

        logger.info(f"Finalized combat session {session_id}")

    def _generate_debug_report(self, session_id: str, output_path: Path) -> None:
        """Generate human-readable debug report.

        Args:
            session_id: Combat session ID
            output_path: Where to save report
        """
        report_file = output_path / "debug_log.txt"

        with open(report_file, "w", encoding="utf-8") as f:
            f.write(f"Combat Session Debug Report\n")
            f.write(f"Session ID: {session_id}\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write("=" * 60 + "\n\n")

            # Add metrics summary
            if session_id in self.metrics:
                metrics = self.metrics[session_id]
                f.write(f"Performance Metrics:\n")
                f.write(f"  Total Events: {metrics.total_events}\n")
                f.write(f"  Total Actions: {metrics.total_actions}\n")
                f.write(f"  Total Dice Rolls: {metrics.total_dice_rolls}\n")
                f.write(f"  Avg Response Time: {metrics.avg_response_time_ms:.2f}ms\n")
                f.write(f"  Total Errors: {metrics.total_errors}\n")
                f.write(f"  Total Warnings: {metrics.total_warnings}\n")
                f.write("\n")

            # Add event summary
            if session_id in self.active_logs:
                f.write(f"Event Log ({len(self.active_logs[session_id])} events):\n")
                f.write("-" * 60 + "\n")

                for event in self.active_logs[session_id]:
                    f.write(f"\n[{event.timestamp.strftime('%H:%M:%S')}] ")
                    f.write(f"{event.event_type.upper()}\n")

                    if event.user_input:
                        f.write(f"  User: {event.user_input}\n")

                    if event.agent_name:
                        f.write(f"  Agent: {event.agent_name}")
                        if event.model_used:
                            f.write(f" ({event.model_used})")
                        if event.processing_time_ms:
                            f.write(f" - {event.processing_time_ms}ms")
                        f.write("\n")

                    if event.dice_rolls:
                        for roll in event.dice_rolls:
                            f.write(f"  Dice: {roll.get('expression')} = ")
                            f.write(f"{roll.get('total')}")
                            if roll.get('critical'):
                                f.write(" CRITICAL!")
                            f.write("\n")

                    if event.errors:
                        for error in event.errors:
                            f.write(f"  ERROR: {error}\n")

                    if event.warnings:
                        for warning in event.warnings:
                            f.write(f"  WARNING: {warning}\n")

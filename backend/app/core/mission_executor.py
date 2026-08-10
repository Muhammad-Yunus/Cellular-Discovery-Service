import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Callable, Optional

from fastapi import HTTPException

from app.api.routers.ws_mission import broadcast_mission_event
from app.cli import CLIAdapter
from app.config.settings import get_settings
from app.db.models import Mission, MissionLog
from app.schemas.mission_log import MissionLogsResponse
from app.db.session import SessionLocal
from app.gps import GPSProvider, GPSError, create_gps_provider
from app.repositories import MissionLocationRepository, MissionRepository, MissionLogRepository
from app.services import ScanService
from app.utils.geo import haversine

logger = logging.getLogger(__name__)

EVENT_TYPES = {
    "STARTING", "RUNNING", "PAUSED", "RESUMED", "VISITED", "SKIPPED",
    "STOPPED", "COMPLETED", "FAILED", "GPS_ERROR", "SCAN_ERROR", "INFO",
}


class MissionExecutor:
    def __init__(
        self,
        gps_provider: Optional[GPSProvider] = None,
        scan_service_factory: Optional[Callable] = None,
        session_factory: Optional[Callable] = None,
    ):
        self.active_tasks: dict[int, asyncio.Task] = {}
        self.lock = asyncio.Lock()
        self.start_lock = asyncio.Lock()
        self.gps_provider = gps_provider or create_gps_provider(
            provider_type=get_settings().GPS_PROVIDER
        )
        self.logs: dict[int, deque] = defaultdict(
            lambda: deque(maxlen=get_settings().MISSION_LOG_SIZE)
        )
        self.gps_failures: dict[int, int] = defaultdict(int)
        self.last_errors: dict[int, str] = {}
        self._shutdown = False
        self._scan_factory = scan_service_factory or self._make_scan_service
        self._session_factory = session_factory or SessionLocal
        # Log sampling: throttle INFO logs to avoid spam (per mission)
        # Each mission keeps track of the last INFO log timestamp + last distance
        # for distance-based threshold (only log if distance changed significantly)
        self._last_info_log: dict[int, datetime] = {}
        self._last_info_distance: dict[int, float] = {}
        self._info_log_interval_sec: float = 5.0
        self._info_distance_threshold_m: float = 2.0

    def _make_scan_service(self, db):
        settings = get_settings()
        return ScanService(
            db=db,
            cli_adapter=CLIAdapter(command=settings.CLI_COMMAND),
            gps_provider=self.gps_provider,
        )

    def _log(self, mission_id: int, event_type: str, message: str) -> None:
        timestamp = datetime.now(timezone.utc)
        # Log sampling for INFO logs: skip if last INFO was <5s ago
        # AND distance hasn't changed by ≥2m (avoid spam from polling loop)
        if event_type == "INFO":
            last_ts = self._last_info_log.get(mission_id)
            if last_ts is not None:
                elapsed = (timestamp - last_ts).total_seconds()
                # Try to extract distance from message ("Target TWR-XXX at X.Xm")
                dist_match = None
                try:
                    msg_tokens = message.split(" at ")
                    if len(msg_tokens) > 1:
                        dist_str = msg_tokens[-1].rstrip("m").strip()
                        dist_match = float(dist_str)
                except (ValueError, IndexError):
                    dist_match = None
                dist_changed = dist_match is not None and abs(
                    dist_match - self._last_info_distance.get(mission_id, -1.0)
                ) >= self._info_distance_threshold_m
                if elapsed < self._info_log_interval_sec and not dist_changed:
                    return  # Skip - within sampling window and no significant change
            self._last_info_log[mission_id] = timestamp
            if dist_match is not None:
                self._last_info_distance[mission_id] = dist_match
        # In-memory cache for fast access (bounded by MISSION_LOG_SIZE)
        self.logs[mission_id].append(
            {
                "timestamp": timestamp.isoformat(),
                "event_type": event_type,
                "message": message,
            }
        )
        # Persist to database so logs survive server restarts
        try:
            db = self._session_factory()
            try:
                MissionLogRepository(db).create(
                    mission_id=mission_id,
                    timestamp=timestamp,
                    event_type=event_type,
                    message=message,
                )
            finally:
                db.close()
        except Exception:
            logger.exception("Failed to persist mission log to database")

    async def _emit(self, event_type: str, mission_id: int, **data) -> None:
        try:
            await broadcast_mission_event(event_type, mission_id, **data)
        except Exception:
            logger.exception("Mission WS broadcast failed")

    async def startup(self) -> None:
        """Restore missions left in STARTING/RUNNING/PAUSED to STOPPED (app restart recovery)."""
        db = self._session_factory()
        try:
            rows = (
                db.query(Mission)
                .filter(Mission.status.in_(("STARTING", "RUNNING", "PAUSED")))
                .all()
            )
            for m in rows:
                m.status = "STOPPED"
                m.stopped_at = datetime.now(timezone.utc)
                self._log(m.id, "STOPPED", "Mission restored to STOPPED on app startup")
            db.commit()
            # Also clear any in-memory tasks that reference deleted or unknown missions.
            # If the DB no longer has the mission but the executor still has a task,
            # cancel it so it doesn't block future starts.
            for mid in list(self.active_tasks.keys()):
                mission = MissionRepository(db).get_by_id(mid)
                if mission is None or mission.status not in ("STARTING", "RUNNING", "PAUSED"):
                    task = self.active_tasks.pop(mid, None)
                    if task and not task.done():
                        task.cancel()
        finally:
            db.close()

    async def shutdown(self) -> None:
        self._shutdown = True
        tasks = list(self.active_tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.active_tasks.clear()

    # ----- helpers (each opens/closes its own DB session) -----

    def _load_mission(self, mission_id: int) -> Optional[SimpleNamespace]:
        db = self._session_factory()
        try:
            mission = MissionRepository(db).get_by_id(mission_id)
            if mission is None:
                return None
            return SimpleNamespace(
                id=mission.id,
                status=mission.status,
                radius_meters=mission.radius_meters,
                total_locations=mission.total_locations,
                visited_locations=mission.visited_locations,
                current_location_id=mission.current_location_id,
            )
        finally:
            db.close()

    def _load_next_pending(self, mission_id: int):
        db = self._session_factory()
        try:
            target = MissionLocationRepository(db).get_next_pending(mission_id)
            if target is None:
                return None
            return SimpleNamespace(
                id=target.id,
                cellular_tower_id=target.cellular_tower_id,
                cellular_tower_name=target.cellular_tower_name,
                latitude=target.latitude,
                longitude=target.longitude,
            )
        finally:
            db.close()

    async def _read_gps(self):
        try:
            return await asyncio.to_thread(self.gps_provider.get_location)
        except GPSError:
            return None

    async def _gps_ok(self, timeout: float):
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self.gps_provider.get_location), timeout=timeout
            )
        except asyncio.TimeoutError as e:
            raise GPSError("GPS read timed out") from e
        except GPSError:
            raise

    async def _handle_gps_failure(self, mission_id: int) -> bool:
        self.gps_failures[mission_id] += 1
        count = self.gps_failures[mission_id]
        threshold = get_settings().MISSION_GPS_FAILURE_THRESHOLD
        self._log(mission_id, "GPS_ERROR", f"GPS read failed ({count}/{threshold})")
        if count >= threshold:
            await self._fail(mission_id, "GPS failure threshold exceeded")
            return True
        return False

    async def _fail(self, mission_id: int, reason: str) -> None:
        self.last_errors[mission_id] = reason
        db = self._session_factory()
        try:
            repo = MissionRepository(db)
            mission = repo.get_by_id(mission_id)
            if mission and mission.status in ("STARTING", "RUNNING", "PAUSED"):
                repo.set_status(mission_id, "FAILED")
                self._log(mission_id, "FAILED", reason)
                await self._emit(
                    "mission_failed",
                    mission_id,
                    status="FAILED",
                    reason=reason,
                )
        finally:
            db.close()

    async def _complete(self, mission_id: int) -> None:
        db = self._session_factory()
        try:
            mission = MissionRepository(db).get_by_id(mission_id)
            # Guard: only complete if still RUNNING (prevent race where stop
            # already set a terminal state).
            if mission.status not in ("RUNNING", "STARTING"):
                self._log(
                    mission_id, mission.status.upper(),
                    f"Skip _complete: mission already in {mission.status}",
                )
                return
            mission.status = "COMPLETED"
            mission.completed_at = completed_at = datetime.now(timezone.utc)
            visited = mission.visited_locations
            db.commit()
        finally:
            db.close()
        self._log(mission_id, "COMPLETED", "All locations visited")
        await self._emit(
            "mission_completed",
            mission_id,
            status="COMPLETED",
            visited_locations=visited,
            completed_at=completed_at.isoformat(),
        )

    def _run_scan(self, port: str, timeout: int, mission_location_id: int):
        db = self._session_factory()
        try:
            service = self._scan_factory(db)
            return service.execute_scan(
                port=port,
                timeout=timeout,
                mission_location_id=mission_location_id,
            )
        finally:
            db.close()

    async def _visit(self, mission_id: int, target, dist: float) -> None:
        db = self._session_factory()
        try:
            mission = MissionRepository(db).get_by_id(mission_id)
            port = mission.tty_port or get_settings().DEFAULT_TTY
            tty_override = mission.tty_port is not None
        finally:
            db.close()

        if not tty_override:
            logger.warning(
                f"Mission {mission_id} falling back to DEFAULT_TTY={get_settings().DEFAULT_TTY}"
            )
            self._log(
                mission_id,
                "INFO",
                f"No tty_port override, using DEFAULT_TTY={get_settings().DEFAULT_TTY}",
            )

        try:
            scan = await asyncio.to_thread(
                self._run_scan,
                port=port,
                timeout=get_settings().MISSION_CLI_TIMEOUT,
                mission_location_id=target.id,
            )
            # Respect pause/stop during the blocking scan
            mission = self._load_mission(mission_id)
            if mission is None or mission.status != "RUNNING":
                return
        except Exception as e:
            self._log(
                mission_id,
                "SCAN_ERROR",
                f"Scan failed for {target.cellular_tower_id}: {e}",
            )
            db = self._session_factory()
            try:
                MissionLocationRepository(db).mark_skipped(mission_id, target.id)
            finally:
                db.close()
            await self._emit(
                "mission_skipped",
                mission_id,
                location_id=target.id,
                tower_id=target.cellular_tower_id,
                reason="SCAN_ERROR",
            )
            return

        db = self._session_factory()
        try:
            repo = MissionRepository(db)
            loc_repo = MissionLocationRepository(db)
            loc_repo.mark_visited(mission_id, target.id, scan.id)
            mission = repo.get_by_id(mission_id)
            mission.visited_locations += 1
            mission.current_location_id = target.id
            db.commit()
        finally:
            db.close()
        self._log(
            mission_id,
            "VISITED",
            f"{target.cellular_tower_id} scanned, session {scan.id} linked",
        )
        await self._emit(
            "mission_visit",
            mission_id,
            location_id=target.id,
            tower_id=target.cellular_tower_id,
            tower_name=target.cellular_tower_name,
            scan_session_id=scan.id,
            distance_m=round(dist, 2),
        )

    # ----- main loop -----

    async def _run(self, mission_id: int) -> None:
        async with self.lock:
            try:
                while not self._shutdown:
                    mission = self._load_mission(mission_id)
                    if mission is None:
                        break
                    if mission.status == "PAUSED":
                        self._log(mission_id, "PAUSED", "Mission paused")
                        await asyncio.sleep(get_settings().MISSION_POLL_INTERVAL)
                        continue
                    if mission.status != "RUNNING":
                        break

                    location = await self._read_gps()
                    if location is None:
                        if await self._handle_gps_failure(mission_id):
                            break
                        await asyncio.sleep(get_settings().MISSION_POLL_INTERVAL)
                        continue
                    self.gps_failures.pop(mission_id, None)

                    target = self._load_next_pending(mission_id)
                    if target is None:
                        await self._complete(mission_id)
                        break

                    dist = haversine(
                        location.latitude,
                        location.longitude,
                        target.latitude,
                        target.longitude,
                    )
                    await self._emit(
                        "mission_progress",
                        mission_id,
                        current_location_id=mission.current_location_id,
                        visited_locations=mission.visited_locations,
                        total_locations=mission.total_locations,
                        status=mission.status,
                        distance_to_target_meters=round(dist, 2),
                    )

                    radius = (
                        mission.radius_meters
                        or get_settings().MISSION_DEFAULT_RADIUS_METERS
                    )
                    if dist <= radius:
                        await self._visit(mission_id, target, dist)
                    else:
                        self._log(
                            mission_id,
                            "INFO",
                            f"Target {target.cellular_tower_id} at {round(dist, 1)}m",
                        )

                    # Re-check status after each iteration so pause/stop are respected
                    mission = self._load_mission(mission_id)
                    if mission is None:
                        break
                    # PAUSED is handled above with sleep+continue; only break for
                    # terminal states (STOPPED / COMPLETED / FAILED) or if not RUNNING.
                    if mission.status not in ("RUNNING", "PAUSED"):
                        break
            except asyncio.CancelledError:
                raise
            except Exception as e:
                await self._fail(mission_id, f"Fatal error: {e}")
            finally:
                self.active_tasks.pop(mission_id, None)

    # ----- control -----

    async def start(self, mission_id: int) -> dict:
        async with self.start_lock:
            db = self._session_factory()
            try:
                repo = MissionRepository(db)
                # Purge any in-memory tasks for missions no longer in the DB, no
                # longer in a transitional state, or already finished — protects
                # against stale state left behind by tests that delete or mutate
                # missions without waiting for task cleanup.
                for stale_id in list(self.active_tasks.keys()):
                    stale = MissionRepository(db).get_by_id(stale_id)
                    task = self.active_tasks.get(stale_id)
                    is_finished = task is None or task.done()
                    db_missing = stale is None
                    not_running = stale is not None and stale.status not in (
                        "STARTING", "RUNNING", "PAUSED"
                    )
                    if is_finished or db_missing or not_running:
                        self.active_tasks.pop(stale_id, None)
                        if task and not task.done():
                            task.cancel()
                mission = repo.get_by_id(mission_id)
                if not mission:
                    raise HTTPException(404, "Mission not found")
                # Status check FIRST so that PAUSED/STOPPED/COMPLETED/FAILED missions
                # get a precise error message instead of the generic "already running".
                if mission.status not in ("IDLE", "READY"):
                    raise HTTPException(
                        409, f"Cannot start mission while it is {mission.status}"
                    )
                if repo.get_running_count() > 0:
                    raise HTTPException(409, "Another mission is already running")
                if mission_id in self.active_tasks:
                    raise HTTPException(409, "Mission is already running")
                if not MissionLocationRepository(db).has_planned_locations(mission_id):
                    raise HTTPException(
                        422, "Mission has no planned locations. Run plan first"
                    )

                repo.set_status(mission_id, "STARTING")
                mission = repo.get_by_id(mission_id)
                mission.started_at = None
                db.commit()
                self._log(mission_id, "STARTING", f"Mission {mission_id} starting")

                try:
                    await self._gps_ok(
                        timeout=get_settings().MISSION_START_GPS_TIMEOUT
                    )
                except GPSError:
                    repo.set_status(mission_id, "FAILED")
                    self.last_errors[mission_id] = "GPS not available at startup"
                    self._log(mission_id, "FAILED", "GPS not available at startup")
                    raise HTTPException(503, "GPS not available")

                mission = repo.get_by_id(mission_id)
                mission_name = mission.name
                total_locations = mission.total_locations
                mission.status = "RUNNING"
                mission.started_at = started_at = datetime.now(timezone.utc)
                db.commit()
            finally:
                db.close()

            self.active_tasks[mission_id] = asyncio.create_task(
                self._run(mission_id)
            )
            await self._emit(
                "mission_started",
                mission_id,
                name=mission_name,
                status="RUNNING",
                total_locations=total_locations,
                started_at=started_at.isoformat(),
            )
            return {
                "message": "Mission started",
                "mission_id": mission_id,
                "status": "RUNNING",
            }

    async def pause(self, mission_id: int) -> dict:
        db = self._session_factory()
        try:
            repo = MissionRepository(db)
            mission = repo.get_by_id(mission_id)
            if not mission:
                raise HTTPException(404, "Mission not found")
            if mission.status != "RUNNING":
                raise HTTPException(
                    409, f"Cannot pause mission while it is {mission.status}"
                )
            repo.set_status(mission_id, "PAUSED")
            self._log(mission_id, "PAUSED", "Mission paused")
            await self._emit("mission_paused", mission_id, status="PAUSED")
            return {"message": "Mission paused", "status": "PAUSED"}
        finally:
            db.close()

    async def resume(self, mission_id: int) -> dict:
        db = self._session_factory()
        try:
            repo = MissionRepository(db)
            mission = repo.get_by_id(mission_id)
            if not mission:
                raise HTTPException(404, "Mission not found")
            if mission.status != "PAUSED":
                raise HTTPException(
                    409, f"Cannot resume mission while it is {mission.status}"
                )
            repo.set_status(mission_id, "RUNNING")
            self._log(mission_id, "RESUMED", "Mission resumed")
            await self._emit("mission_resumed", mission_id, status="RUNNING")
            return {"message": "Mission resumed", "status": "RUNNING"}
        finally:
            db.close()

    async def stop(self, mission_id: int) -> dict:
        db = self._session_factory()
        try:
            repo = MissionRepository(db)
            mission = repo.get_by_id(mission_id)
            if not mission:
                raise HTTPException(404, "Mission not found")
            if mission.status not in ("STARTING", "RUNNING", "PAUSED"):
                raise HTTPException(
                    409, f"Cannot stop mission while it is {mission.status}"
                )
            mission.status = "STOPPED"
            mission.stopped_at = stopped_at = datetime.now(timezone.utc)
            db.commit()
            self._log(mission_id, "STOPPED", "Mission stopped")
        finally:
            db.close()

        task = self.active_tasks.get(mission_id)
        if task is not None:
            task.cancel()
        await self._emit(
            "mission_stopped",
            mission_id,
            status="STOPPED",
            stopped_at=stopped_at.isoformat(),
        )
        return {"message": "Mission stopped", "status": "STOPPED"}

    def get_status(self, mission_id: int) -> dict:
        db = self._session_factory()
        try:
            mission = MissionRepository(db).get_by_id(mission_id)
            if not mission:
                raise HTTPException(404, "Mission not found")
            progress = (
                mission.visited_locations / mission.total_locations * 100
                if mission.total_locations > 0
                else 0.0
            )
            return {
                "mission_id": mission.id,
                "name": mission.name,
                "status": mission.status,
                "started_at": mission.started_at,
                "completed_at": mission.completed_at,
                "stopped_at": mission.stopped_at,
                "total_locations": mission.total_locations,
                "visited_locations": mission.visited_locations,
                "progress_percent": round(progress, 1),
                "current_location_id": mission.current_location_id,
                "active": mission.id in self.active_tasks,
                "gps_failure_count": self.gps_failures.get(mission_id, 0),
                "last_error": self.last_errors.get(mission_id),
            }
        finally:
            db.close()

    def get_logs(self, mission_id: int, page: int = 1, page_size: int = 10) -> dict:
        """
        Get paginated logs for a mission, sourced from the database so logs
        survive server restarts.

        Args:
            mission_id: ID of the mission
            page: Page number (1-indexed, default: 1)
            page_size: Items per page (default: 10, max: 100)

        Returns:
            Dictionary with 'items', 'total', 'page', 'page_size', 'total_pages'
        """
        db = self._session_factory()
        try:
            mission = MissionRepository(db).get_by_id(mission_id)
            if not mission:
                raise HTTPException(404, "Mission not found")

            log_repo = MissionLogRepository(db)
            total = log_repo.count_by_mission_id(mission_id)

            # Calculate pagination
            page_size = min(page_size, 100)  # Cap at 100
            total_pages = max(1, (total + page_size - 1) // page_size)

            # Return empty if page exceeds total
            if page > total_pages:
                return MissionLogsResponse(
                    items=[],
                    total=total,
                    page=page,
                    page_size=page_size,
                    total_pages=total_pages
                )

            # Fetch the requested page (DESC by timestamp)
            offset = (page - 1) * page_size
            db_logs = (
                db.query(MissionLog)
                .filter(MissionLog.mission_id == mission_id)
                .order_by(MissionLog.timestamp.desc())
                .offset(offset)
                .limit(page_size)
                .all()
            )

            items = [
                {
                    "timestamp": log.timestamp.isoformat(),
                    "event_type": log.event_type,
                    "message": log.message,
                }
                for log in db_logs
            ]

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            }
        finally:
            db.close()

## Player Seat Flow TODO

- [x] Wire `PlayerPage` into `RoomProvider` and derive the current user’s seat state.
- [x] Build `SeatSelectionModal` for players (reuse `SeatCard`, handle occupy flow).
- [x] Build `CharacterAssignmentModal` that reuses the DM character creation UI and calls `assignCharacterToSeat`.
- [x] Add vacate/reconnect handling (PlayerVacatedModal + seat re-evaluation on reconnect).
- [x] Integrate the new modals into `PlayerPage` state transitions so ready players drop into `PlayerView`.

# Rooming

Rooming is an operational domain separate from commercial accommodation sales. The backend will
validate assignments using required beds, available standard and extra beds, trip-hotel stay
dates, and booked accommodation. The drag-and-drop interface will remain a client of those rules.

Phase 4 establishes the underlying catalog distinction: `RoomType` is what is sold, while `Room`
is a physical operational resource. Physical rooms store standard and permitted extra beds, but
occupant and no-bed-child rules remain part of the later rooming domain.

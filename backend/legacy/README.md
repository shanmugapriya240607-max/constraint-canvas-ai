# Archived prototype (not active)

The original app modules and tests are preserved unchanged for historical review.
They are not imported by the Phase 1 app or collected by its pytest configuration.
Their imports refer to the old app layout; this is a reference archive, not a runnable
second application. Do not install Gemini or OR-Tools to run the foundation.

Candidates for later removal after review: all files under legacy/app/ and
legacy/tests/, including the previous entry point, SolveRun database code,
planning schemas, parser, solver, priority engine, validator, and their tests.
No old database or .env file was removed.

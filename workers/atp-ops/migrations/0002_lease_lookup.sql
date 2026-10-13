-- Preserve the immutable v1 migration; lease-token lookup must not scan history.
CREATE INDEX ops_events_lease_token ON ops_events(lease_token);

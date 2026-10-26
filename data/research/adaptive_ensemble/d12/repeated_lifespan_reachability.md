# Repeated lifespan reachability

`app.lifespan` can run more than once in the same process. That is source-reachable. It is not the normal production pattern of one process and one lifespan.

Global Telegram state and the database globals survive the first lifespan. A timed-out worker survives it. The next start is refused. The application still yields. The later stop acts on the old worker. After that worker exits, a third lifespan can start a new worker. The database connection id was the same across the first two lifespans.

`NO_DUPLICATE_WORKER` was observed. It does not mean the application reported the Telegram start status.

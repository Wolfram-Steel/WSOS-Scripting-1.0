"""Ejecución paralela con parada responsable (compartida por búsqueda y scraping)."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

POLL_SECONDS = 0.25


def run_parallel(items, worker, *, max_workers, stop_event=None, progress=None,
                 label="Progreso", on_error=None):
    """Ejecuta ``worker(item)`` en paralelo con una ventana acotada de tareas.

    La ventana de futuros pendientes nunca supera el número de workers. Esto evita
    crear miles de ``Future`` cuando una búsqueda sucia o una categoría contiene
    muchas URLs, reduce consumo de memoria y hace que la parada deje menos trabajo
    pendiente. Los resultados siguen devolviéndose en el orden original.
    """
    items = list(items)
    results = [None] * len(items)
    if not items:
        return results

    workers = max(1, min(int(max_workers), len(items)))
    executor = ThreadPoolExecutor(max_workers=workers)
    pending = {}
    next_index = 0
    completed = 0

    def submit_next():
        nonlocal next_index
        if next_index >= len(items):
            return False
        idx = next_index
        next_index += 1
        pending[executor.submit(worker, items[idx])] = idx
        return True

    for _ in range(workers):
        submit_next()

    def collect(done_futures):
        nonlocal completed
        for future in done_futures:
            idx = pending.pop(future)
            if future.cancelled():
                continue
            try:
                results[idx] = future.result()
            except Exception as exc:  # noqa: BLE001 - el worker no debe tumbar el pool
                print(f"  [!] Error procesando {items[idx]!r}: {exc}")
                results[idx] = on_error(items[idx], exc) if on_error else None
            completed += 1
            if progress:
                progress(completed, len(items), f"{label}: {completed}/{len(items)}")
            if not (stop_event and stop_event.is_set()):
                submit_next()

    try:
        while pending:
            if stop_event and stop_event.is_set():
                print("\n[!] Proceso detenido por el usuario.")
                for future in list(pending):
                    future.cancel()
                collect([f for f in list(pending) if f.done() and not f.cancelled()])
                break
            done, _ = wait(set(pending), timeout=POLL_SECONDS, return_when=FIRST_COMPLETED)
            if done:
                collect(done)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    return results

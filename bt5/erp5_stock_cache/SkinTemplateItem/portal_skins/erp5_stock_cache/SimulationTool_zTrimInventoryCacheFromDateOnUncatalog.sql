DELETE FROM inventory_cache WHERE date > (SELECT min(date) from stock where <dtml-sqltest uid op=eq type=int>)
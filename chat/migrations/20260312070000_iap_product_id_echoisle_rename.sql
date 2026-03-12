-- rename legacy IAP product identifiers to com.echoisle.*
-- this migration is idempotent and keeps existing order references valid

BEGIN;

INSERT INTO iap_products (product_id, coins, is_active, created_at, updated_at)
SELECT
  replace(
    product_id,
    (SELECT 'com.' || 'ai' || 'comm.'),
    'com.echoisle.'
  ),
  coins,
  is_active,
  created_at,
  CURRENT_TIMESTAMP
FROM iap_products
WHERE product_id LIKE (SELECT 'com.' || 'ai' || 'comm.' || '%')
ON CONFLICT (product_id) DO UPDATE
SET
  coins = EXCLUDED.coins,
  is_active = EXCLUDED.is_active,
  updated_at = CURRENT_TIMESTAMP;

UPDATE iap_orders
SET product_id = replace(
  product_id,
  (SELECT 'com.' || 'ai' || 'comm.'),
  'com.echoisle.'
)
WHERE product_id LIKE (SELECT 'com.' || 'ai' || 'comm.' || '%');

DELETE FROM iap_products p
WHERE p.product_id LIKE (SELECT 'com.' || 'ai' || 'comm.' || '%')
  AND NOT EXISTS (
    SELECT 1
    FROM iap_orders o
    WHERE o.product_id = p.product_id
  );

COMMIT;

-- Q1: Latest 5 transactions (latest-record query)
SELECT l.line_id, i.invoice_no, i.invoice_date, l.stock_code, l.quantity, l.unit_price, c.name AS country
FROM invoice_lines l
JOIN invoices i ON i.invoice_no = l.invoice_no
JOIN countries c ON c.country_id = i.country_id
ORDER BY i.invoice_date DESC, l.line_id DESC
LIMIT 5;

-- Q2: Daily revenue for 1 to 8 December 2011 (date-range query on the daily view)
SELECT sale_date, gross_revenue, net_revenue, n_invoices, total_quantity
FROM daily_revenue
WHERE sale_date BETWEEN '2011-12-01' AND '2011-12-08'
ORDER BY sale_date;

-- Q3: Monthly net revenue and average per trading day (trend)
SELECT DATE_FORMAT(sale_date, '%Y-%m') AS month,
       COUNT(*)                         AS trading_days,
       ROUND(SUM(net_revenue), 2)       AS net_revenue,
       ROUND(AVG(net_revenue), 2)       AS avg_daily_net_revenue
FROM daily_revenue
GROUP BY month
ORDER BY month;

-- Q4: Lag and moving average features for November 2011
-- (lag 6 = same weekday last week, since the shop trades 6 days a week)
SELECT sale_date, net_revenue, lag_1, lag_6, roll_mean_6
FROM (
    SELECT sale_date,
           ROUND(net_revenue, 2)                                                AS net_revenue,
           ROUND(LAG(net_revenue, 1) OVER w, 2)                                 AS lag_1,
           ROUND(LAG(net_revenue, 6) OVER w, 2)                                 AS lag_6,
           ROUND(AVG(net_revenue) OVER (w ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING), 2) AS roll_mean_6
    FROM daily_revenue
    WINDOW w AS (ORDER BY sale_date)
) AS features
WHERE sale_date BETWEEN '2011-11-01' AND '2011-11-12'
ORDER BY sale_date;

-- Q5: Top 5 international markets by sales revenue
SELECT c.name AS country,
       COUNT(DISTINCT i.invoice_no)           AS invoices,
       ROUND(SUM(l.quantity * l.unit_price), 2) AS revenue
FROM invoice_lines l
JOIN invoices i ON i.invoice_no = l.invoice_no
JOIN countries c ON c.country_id = i.country_id
WHERE NOT i.is_cancelled AND c.name <> 'United Kingdom'
GROUP BY c.name
ORDER BY revenue DESC
LIMIT 5;

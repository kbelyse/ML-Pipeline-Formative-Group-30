// MongoDB queries for the Online Retail time-series pipeline.
// Run with: mongosh retail database/mongodb/queries.js

const show = (title, result) => {
  print(`\n${title}`);
  printjson(result);
};

// Q1: Latest record
show("Q1: Latest record",
  db.transactions.find({}, { _id: 0 }).sort({ invoice_date: -1, _id: -1 }).limit(1).toArray());

// Q2: Records in a date range (1 to 8 December 2011): count and first 3
const range = { invoice_date: { $gte: ISODate("2011-12-01"), $lt: ISODate("2011-12-09") } };
show("Q2: Records between 2011-12-01 and 2011-12-08", {
  count: db.transactions.countDocuments(range),
  first_3: db.transactions.find(range, { _id: 0, invoice_no: 1, invoice_date: 1, "product.stock_code": 1, quantity: 1, revenue: 1 })
    .sort({ invoice_date: 1 }).limit(3).toArray(),
});

// Q3: Daily net revenue for the same range (time-series aggregation)
show("Q3: Daily revenue between 2011-12-01 and 2011-12-08", db.transactions.aggregate([
  { $match: range },
  { $group: {
      _id: { $dateToString: { format: "%Y-%m-%d", date: "$invoice_date" } },
      gross_revenue: { $sum: { $cond: ["$is_cancelled", 0, "$revenue"] } },
      net_revenue: { $sum: "$revenue" },
      lines: { $sum: 1 } } },
  { $project: { _id: 0, date: "$_id", gross_revenue: { $round: ["$gross_revenue", 2] },
                net_revenue: { $round: ["$net_revenue", 2] }, lines: 1 } },
  { $sort: { date: 1 } },
]).toArray());

// Q4: 6-day moving average of daily net revenue in November 2011 ($setWindowFields)
show("Q4: Daily net revenue with 6-day moving average (November 2011, first 10 days)", db.transactions.aggregate([
  { $match: { invoice_date: { $gte: ISODate("2011-10-20"), $lt: ISODate("2011-12-01") } } },
  { $group: { _id: { $dateTrunc: { date: "$invoice_date", unit: "day" } }, net_revenue: { $sum: "$revenue" } } },
  { $setWindowFields: {
      sortBy: { _id: 1 },
      output: { roll_mean_6: { $avg: "$net_revenue", window: { documents: [-6, -1] } } } } },
  { $match: { _id: { $gte: ISODate("2011-11-01") } } },
  { $project: { _id: 0, date: { $dateToString: { format: "%Y-%m-%d", date: "$_id" } },
                net_revenue: { $round: ["$net_revenue", 2] }, roll_mean_6: { $round: ["$roll_mean_6", 2] } } },
  { $limit: 10 },
]).toArray());

// Q5: Top 5 products by quantity sold in November 2011
show("Q5: Top 5 products by quantity sold in November 2011", db.transactions.aggregate([
  { $match: { is_cancelled: false, invoice_date: { $gte: ISODate("2011-11-01"), $lt: ISODate("2011-12-01") } } },
  { $group: { _id: "$product.stock_code", description: { $first: "$product.description" },
              quantity: { $sum: "$quantity" }, revenue: { $sum: "$revenue" } } },
  { $sort: { quantity: -1 } },
  { $limit: 5 },
  { $project: { _id: 0, stock_code: "$_id", description: 1, quantity: 1, revenue: { $round: ["$revenue", 2] } } },
]).toArray());

// MongoDB collection design for the Online Retail time-series pipeline.
// Run with: mongosh retail database/mongodb/collection_setup.js
//
// Collection `transactions`: one document per invoice line. The customer and
// product are embedded because they are always read together with the line and
// are small, so one read returns a complete record without joins.

db.transactions.drop();

db.createCollection("transactions", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["invoice_no", "invoice_date", "is_cancelled", "customer", "product",
                 "quantity", "unit_price", "revenue"],
      properties: {
        invoice_no: { bsonType: "string" },
        invoice_date: { bsonType: "date" },
        is_cancelled: { bsonType: "bool" },
        customer: {
          bsonType: "object",
          required: ["customer_id", "country"],
          properties: {
            customer_id: { bsonType: "string" },
            country: { bsonType: "string" },
          },
        },
        product: {
          bsonType: "object",
          required: ["stock_code"],
          properties: {
            stock_code: { bsonType: "string" },
            description: { bsonType: ["string", "null"] },
          },
        },
        quantity: { bsonType: "int" },
        unit_price: { bsonType: "double", minimum: 0, exclusiveMinimum: true },
        revenue: { bsonType: "double" },
      },
    },
  },
});

// Date index supports the latest-record and date-range queries
db.transactions.createIndex({ invoice_date: -1 });
db.transactions.createIndex({ invoice_no: 1 });
db.transactions.createIndex({ "customer.customer_id": 1 });

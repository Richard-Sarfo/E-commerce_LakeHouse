# Glue Data Catalog tables for the three Delta Lake datasets.
#
# Athena's native Delta reader (engine v3) recognizes a Glue table as Delta
# only when it has the exact shape produced by `CREATE EXTERNAL TABLE x
# LOCATION '...' TBLPROPERTIES ('table_type'='DELTA')`. The required shape
# (confirmed by reading back a table created via Athena DDL):
#
#   - parameters: lower-case "table_type"="delta", "EXTERNAL"="TRUE",
#     "spark.sql.sources.provider"="delta",
#     "spark.sql.partitionProvider"="catalog",
#     "spark.sql.sources.schema.numParts"="1",
#     "spark.sql.sources.schema.part.0"=<Spark struct schema JSON>
#   - ser_de_info.parameters: "serialization.format"="1", "path"=<s3 root>
#   - Storage columns + partition_keys still declared so Athena gets the
#     schema before any read of _delta_log.
#
# A `classification` parameter or upper-case "DELTA" breaks the recognition.

locals {
  # Spark struct schema used in spark.sql.sources.schema.part.0.
  # Each field uses Spark's type names ("integer", "long", "string", "decimal(p,s)").
  spark_schema_products = jsonencode({
    type = "struct"
    fields = [
      { name = "product_id",    type = "integer", nullable = true, metadata = {} },
      { name = "department_id", type = "integer", nullable = true, metadata = {} },
      { name = "department",    type = "string",  nullable = true, metadata = {} },
      { name = "product_name",  type = "string",  nullable = true, metadata = {} },
    ]
  })

  spark_schema_orders = jsonencode({
    type = "struct"
    fields = [
      { name = "order_num",       type = "long",          nullable = true, metadata = {} },
      { name = "order_id",        type = "integer",       nullable = true, metadata = {} },
      { name = "user_id",         type = "integer",       nullable = true, metadata = {} },
      { name = "order_timestamp", type = "string",        nullable = true, metadata = {} },
      { name = "total_amount",    type = "decimal(12,2)", nullable = true, metadata = {} },
      { name = "date",            type = "string",        nullable = true, metadata = {} },
    ]
  })

  spark_schema_order_items = jsonencode({
    type = "struct"
    fields = [
      { name = "id",                     type = "long",    nullable = true, metadata = {} },
      { name = "order_id",               type = "integer", nullable = true, metadata = {} },
      { name = "user_id",                type = "integer", nullable = true, metadata = {} },
      { name = "days_since_prior_order", type = "integer", nullable = true, metadata = {} },
      { name = "product_id",             type = "integer", nullable = true, metadata = {} },
      { name = "add_to_cart_order",      type = "integer", nullable = true, metadata = {} },
      { name = "reordered",              type = "integer", nullable = true, metadata = {} },
      { name = "order_timestamp",        type = "string",  nullable = true, metadata = {} },
      { name = "date",                   type = "string",  nullable = true, metadata = {} },
    ]
  })

  # Common parameter block for every Delta table.
  delta_table_params_common = {
    "EXTERNAL"                          = "TRUE"
    "table_type"                        = "delta"
    "spark.sql.sources.provider"        = "delta"
    "spark.sql.partitionProvider"       = "catalog"
    "spark.sql.sources.schema.numParts" = "1"
  }
}

# ── Products ─────────────────────────────────────────────────────────────────

resource "aws_glue_catalog_table" "products" {
  database_name = aws_glue_catalog_database.lakehouse.name
  name          = "products"
  description   = "Product dimension — department and name per product_id"
  table_type    = "EXTERNAL_TABLE"

  parameters = merge(local.delta_table_params_common, {
    "spark.sql.sources.schema.part.0" = local.spark_schema_products
  })

  storage_descriptor {
    location      = "${local.processed_root}/products/"
    input_format  = "org.apache.hadoop.mapred.SequenceFileInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveSequenceFileOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe"
      parameters = {
        "serialization.format" = "1"
        "path"                 = "${local.processed_root}/products/"
      }
    }

    columns {
      name = "product_id"
      type = "int"
    }
    columns {
      name = "department_id"
      type = "int"
    }
    columns {
      name = "department"
      type = "string"
    }
    columns {
      name = "product_name"
      type = "string"
    }
  }
}

# ── Orders ───────────────────────────────────────────────────────────────────

resource "aws_glue_catalog_table" "orders" {
  database_name = aws_glue_catalog_database.lakehouse.name
  name          = "orders"
  description   = "Order header — one row per order_id"
  table_type    = "EXTERNAL_TABLE"

  parameters = merge(local.delta_table_params_common, {
    "spark.sql.sources.schema.part.0" = local.spark_schema_orders
  })

  storage_descriptor {
    location      = "${local.processed_root}/orders/"
    input_format  = "org.apache.hadoop.mapred.SequenceFileInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveSequenceFileOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe"
      parameters = {
        "serialization.format" = "1"
        "path"                 = "${local.processed_root}/orders/"
      }
    }

    columns {
      name = "order_num"
      type = "bigint"
    }
    columns {
      name = "order_id"
      type = "int"
    }
    columns {
      name = "user_id"
      type = "int"
    }
    columns {
      name = "order_timestamp"
      type = "string"
    }
    columns {
      name = "total_amount"
      type = "decimal(12,2)"
    }
  }

  partition_keys {
    name = "date"
    type = "string"
  }
}

# ── Order Items ──────────────────────────────────────────────────────────────

resource "aws_glue_catalog_table" "order_items" {
  database_name = aws_glue_catalog_database.lakehouse.name
  name          = "order_items"
  description   = "Line-item fact — one row per product per order"
  table_type    = "EXTERNAL_TABLE"

  parameters = merge(local.delta_table_params_common, {
    "spark.sql.sources.schema.part.0" = local.spark_schema_order_items
  })

  storage_descriptor {
    location      = "${local.processed_root}/order_items/"
    input_format  = "org.apache.hadoop.mapred.SequenceFileInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveSequenceFileOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe"
      parameters = {
        "serialization.format" = "1"
        "path"                 = "${local.processed_root}/order_items/"
      }
    }

    columns {
      name = "id"
      type = "bigint"
    }
    columns {
      name = "order_id"
      type = "int"
    }
    columns {
      name = "user_id"
      type = "int"
    }
    columns {
      name = "days_since_prior_order"
      type = "int"
    }
    columns {
      name = "product_id"
      type = "int"
    }
    columns {
      name = "add_to_cart_order"
      type = "int"
    }
    columns {
      name = "reordered"
      type = "int"
    }
    columns {
      name = "order_timestamp"
      type = "string"
    }
  }

  partition_keys {
    name = "date"
    type = "string"
  }
}

# Explicit Glue Data Catalog table definitions for Delta tables.
#
# Rationale: Athena engine v3 reads Delta tables natively when the table
# parameters carry table_type=DELTA. Defining tables in Terraform (rather
# than running a Glue Crawler) gives schema versioning in git and avoids
# the Crawler mis-classifying Delta _delta_log directories.

# ── Products ─────────────────────────────────────────────────────────────────

resource "aws_glue_catalog_table" "products" {
  database_name = aws_glue_catalog_database.lakehouse.name
  name          = "products"
  description   = "Product dimension — department and name per product_id"
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "table_type"                 = "DELTA"
    "spark.sql.sources.provider" = "delta"
    "classification"             = "delta"
    "path"                       = "${local.processed_root}/products/"
  }

  storage_descriptor {
    location      = "${local.processed_root}/products/"
    input_format  = "org.apache.hadoop.mapred.SequenceFileInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveSequenceFileOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe"
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

  parameters = {
    "table_type"                 = "DELTA"
    "spark.sql.sources.provider" = "delta"
    "classification"             = "delta"
    "path"                       = "${local.processed_root}/orders/"
  }

  storage_descriptor {
    location      = "${local.processed_root}/orders/"
    input_format  = "org.apache.hadoop.mapred.SequenceFileInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveSequenceFileOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe"
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
      type = "timestamp"
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

# ── Order Items ───────────────────────────────────────────────────────────────

resource "aws_glue_catalog_table" "order_items" {
  database_name = aws_glue_catalog_database.lakehouse.name
  name          = "order_items"
  description   = "Line-item fact — one row per product per order"
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "table_type"                 = "DELTA"
    "spark.sql.sources.provider" = "delta"
    "classification"             = "delta"
    "path"                       = "${local.processed_root}/order_items/"
  }

  storage_descriptor {
    location      = "${local.processed_root}/order_items/"
    input_format  = "org.apache.hadoop.mapred.SequenceFileInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveSequenceFileOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe"
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
      type = "timestamp"
    }
  }

  partition_keys {
    name = "date"
    type = "string"
  }
}

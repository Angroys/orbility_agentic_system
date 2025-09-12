
# 📋 `discount_rule` Table Explanation

The `discount_rule` table defines how discounts or promotions are structured, stored, and applied in the system.

## 🔑 **Fields**

### `id`

* **Type:** Integer (Primary Key, Auto Increment)
* **Meaning:** Unique internal identifier for each discount rule.
* **Example:** `1`, `42`.


### `code`

* **Type:** Text (often unique, case-insensitive)
* **Meaning:** The promo/discount code a customer or operator enters.
* **Notes:** May be `NULL` if the discount is automatically applied.
* **Example:**

  * `WEEKEND10` → 10% off on weekends.
  * `LOYALTY2025` → loyalty program discount.


### `kind`

* **Type:** Text (Enum-like)
* **Meaning:** Defines how the `value` should be interpreted.
* **Common options:**

  * `percent` → percentage discount.
  * `amount` → fixed amount discount (usually in cents to avoid float errors).
  * `free_minutes` → free parking minutes before tariff applies.
* **Example:** `percent`.


### `value`

* **Type:** Integer
* **Meaning:** The numerical discount amount, interpreted by `kind`.
* **Examples:**

  * If `kind = 'percent'` → `10` means 10% off.
  * If `kind = 'amount'` → `500` means 5.00 MDL off.
  * If `kind = 'free_minutes'` → `30` means 30 minutes free parking.


### `valid_from`

* **Type:** Text (DateTime in ISO-8601 format, e.g., `YYYY-MM-DDTHH:MM:SS`)
* **Meaning:** Start date and time when the discount becomes valid.
* **Notes:** `NULL` means valid immediately.
* **Example:** `2025-09-12T00:00:00`.


### `valid_to`

* **Type:** Text (DateTime in ISO-8601 format, e.g., `YYYY-MM-DDTHH:MM:SS`)
* **Meaning:** End date and time when the discount expires.
* **Notes:** `NULL` means no expiry date (valid indefinitely).
* **Example:** `2025-09-15T00:00:00`.


# ✅ Example Records

| id | code      | kind          | value | valid\_from         | valid\_to           |
| -- | --------- | ------------- | ----- | ------------------- | ------------------- |
| 1  | WEEKEND10 | percent       | 10    | 2025-09-12T00:00:00 | 2025-09-15T00:00:00 |
| 2  | LOYALTY5  | amount        | 500   | NULL                | NULL                |
| 3  | NULL      | free\_minutes | 30    | NULL                | NULL                |

---

# 💳 `payment` Table Explanation

The `payment` table stores information about every payment attempt or confirmation made in the parking system.


## 🔑 **Fields**

### `id`

* **Type:** Integer (Primary Key, Auto Increment)
* **Meaning:** Unique identifier for the payment record.
* **Example:** `101`.


### `session_id`

* **Type:** Integer (Foreign Key → `parking_session.id`)
* **Meaning:** Links the payment to the customer’s **parking session**.
* **Example:** Payment of session `45`.


### `station_id`

* **Type:** Integer (Foreign Key → `equipment.id` or `station table`)
* **Meaning:** Identifies the terminal or station where the payment was made.
* **Examples:**

  * Payment at `POF-01` (Pay-On-Foot terminal).
  * Payment at `Exit-A` terminal.


### `method`

* **Type:** Text
* **Meaning:** How the payment was made.
* **Values:**

  * `cash` → Cash inserted at machine.
  * `card` → Credit/Debit card.
  * `online` → Mobile app / Web payment.


### `amount_cents`

* **Type:** Integer (stored in smallest currency unit, e.g., cents)
* **Meaning:** The payment amount. Using cents avoids floating-point rounding issues.
* **Example:** `500` = 5.00 MDL.


### `approved`

* **Type:** Boolean (0 = not approved, 1 = approved)
* **Meaning:** Whether the payment was successfully authorized.
* **Examples:**

  * `1` → Payment succeeded.
  * `0` → Payment failed / rejected.
  

### `created_at`

* **Type:** Text (ISO-8601 datetime)
* **Meaning:** Timestamp when the payment record was created.
* **Example:** `2025-09-09T14:35:00`.


# ✅ Example Records

| id | session\_id | station\_id | method | amount\_cents | approved | processor\_ref | created\_at         |
| -- | ----------- | ----------- | ------ | ------------- | -------- | -------------- | ------------------- |
| 1  | 45          | 3           | card   | 5000          | 1        | TXN-ABCD123    | 2025-09-09T14:35:00 |
| 2  | 46          | 4           | cash   | 3000          | 1        | NULL           | 2025-09-09T15:12:00 |
| 3  | 47          | 5           | online | 4500          | 0        | TXN-XYZ789     | 2025-09-09T15:30:00 |

---

# 🎟️ `voucher` Table Explanation

The `voucher` table stores prepaid or promotional voucher information that can be used to pay for parking sessions (fully or partially).


## 🔑 **Fields**

### `id`

* **Type:** Integer (Primary Key, Auto Increment)
* **Meaning:** Unique internal identifier for the voucher.
* **Example:** `12`.


### `code`

* **Type:** Text (Unique)
* **Meaning:** Human-readable voucher code customers enter or scan.
* **Usage:** Acts like a “gift card” or promo code.
* **Example:**

  * `FREEPARK2025` → free parking voucher.
  * `GIFT-50MDL` → prepaid balance.


### `balance_cents`

* **Type:** Integer (stored in smallest currency unit, e.g., cents)
* **Meaning:** Remaining balance on the voucher. Decreases as the voucher is used.
* **Example:**

  * `5000` → 50.00 MDL still available.
  * `0` → voucher fully spent.


### `expires_at`

* **Type:** Text (ISO-8601 datetime, e.g., `YYYY-MM-DDTHH:MM:SS`)
* **Meaning:** Date and time until the voucher is valid.
* **Notes:**

  * `NULL` = voucher never expires.
  * Expired vouchers cannot be redeemed.
* **Example:** `2025-12-31T23:59:59`.


# ✅ Example Records

| id | code         | balance\_cents | expires\_at         |
| -- | ------------ | -------------- | ------------------- |
| 1  | FREEPARK2025 | 0              | 2025-06-30T23:59:59 |
| 2  | GIFT-50MDL   | 5000           | NULL                |
| 3  | EVENTPASS123 | 2000           | 2025-09-30T23:59:59 |

---

# ⏱️ `tariff` Table Explanation

The `tariff` table defines the **pricing rules** for parking sessions. Each record describes how much a customer should pay depending on their parking duration.


## 🔑 **Fields**

### `id`

* **Type:** Integer (Primary Key, Auto Increment)
* **Meaning:** Unique identifier for the tariff rule.
* **Example:** `1`.


### `name`

* **Type:** Text
* **Meaning:** Human-readable name of the tariff plan.
* **Usage:** Makes it easy to distinguish between different pricing rules.
* **Examples:**

  * `"Standard Tariff"`
  * `"Weekend Special"`
  * `"VIP Customers"`


### `free_minutes`

* **Type:** Integer
* **Meaning:** Number of minutes of **free parking** before charges apply.
* **Example:**

  * `15` → first 15 minutes are free.
  * `0` → no free time.


### `rate_cents_per_hour`

* **Type:** Integer (stored in cents to avoid floating-point errors)
* **Meaning:** Hourly parking rate applied after the free minutes are consumed.
* **Notes:** Usually prorated to minutes.
* **Example:**

  * `500` → 5.00 MDL per hour.
  * `2000` → 20.00 MDL per hour.


### `max_daily_cents`

* **Type:** Integer (stored in cents)
* **Meaning:** Maximum amount a customer can be charged for **one day** of parking.
* **Purpose:** Prevents very high fees for long stays.
* **Example:**

  * `6000` → 60.00 MDL is the cap for 24h.


# ✅ Example Records

| id | name            | free\_minutes | rate\_cents\_per\_hour | max\_daily\_cents |
| -- | --------------- | ------------- | ---------------------- | ----------------- |
| 1  | Standard Tariff | 15            | 500                    | 6000              |
| 2  | Weekend Special | 30            | 300                    | 4000              |
| 3  | VIP Customers   | 60            | 0                      | 0                 |

---

# 🏢 `station` Table Explanation

The `station` table represents **physical or logical devices** installed in a parking facility (like payment machines, entry/exit terminals). It defines where each device is located and what role it plays.


## 🔑 **Fields**

### `id`

* **Type:** Integer (Primary Key, Auto Increment)
* **Meaning:** Unique identifier of the station in the system.
* **Example:** `7`.


### `kind`

* **Type:** Text (Enum-like)
* **Meaning:** Defines the **type of station**.
* **Common values:**

  * `entry_terminal` → for vehicles entering.
  * `exit_terminal` → for vehicles leaving.
  * `pof` → Pay-On-Foot machine (payment kiosk).


### `label`

* **Type:** Text
* **Meaning:** Human-readable label for the station, making it easier for operators and technicians to identify it.
* **Examples:**

  * `"POF-01"` → Pay-on-foot terminal 1.
  * `"Exit A Terminal"` → Exit station on Lane A.


# ✅ Example Records

| id | zone\_id | kind            | label           |
| -- | -------- | --------------- | --------------- |
| 1  | 1        | entry\_terminal | Entry Lane A    |
| 2  | 1        | exit\_terminal  | Exit Lane A     |
| 3  | 2        | pof             | POF-01          |

---

# 🎫 `ticket` Table Explanation

The `ticket` table stores information about **parking tickets** issued when a vehicle enters the parking facility (usually in ticket-based parking systems).


## 🔑 **Fields**

### `id`

* **Type:** Integer (Primary Key, Auto Increment)
* **Meaning:** Internal system identifier of the ticket record.
* **Example:** `101`.


### `code`

* **Type:** Text (Unique)
* **Meaning:** The actual code printed on the ticket (often barcode/QR).
* **Usage:** Used by terminals and scanners to identify the parking session.
* **Example:** `TCK-20250909-12345`.


### `issued_at`

* **Type:** Text (ISO-8601 datetime, e.g., `YYYY-MM-DDTHH:MM:SS`)
* **Meaning:** The timestamp when the ticket was issued at the entry station.
* **Example:** `2025-09-09T08:15:00`.


### `entry_station`

* **Type:** Integer (Foreign Key → `station.id`)
* **Meaning:** The station (entry terminal) where the ticket was printed.
* **Example:**

  * `1` → Entry Lane A terminal.
  * `2` → Entry Lane B terminal.


### `status`

* **Type:** Text (Enum-like)
* **Meaning:** The current state of the ticket.
* **Values:**

  * `active` → Ticket in use for an open parking session.
  * `paid` → Ticket has been paid, awaiting exit.
  * `closed` → Ticket/session completed. Activated after exit
  * `lost` → Ticket reported as lost by customer/operator.


# ✅ Example Records

| id | code               | issued\_at          | entry\_station | status |
| -- | ------------------ | ------------------- | -------------- | ------ |
| 1  | TCK-20250909-12345 | 2025-09-09T08:15:00 | 1              | active |
| 2  | TCK-20250908-54321 | 2025-09-08T19:00:00 | 2              | paid   |
| 3  | TCK-20250907-11111 | 2025-09-07T10:30:00 | 1              | lost   |

---

# 🚗 `session` Table Explanation

The `session` table stores the **lifecycle of a vehicle’s parking stay**. It ties together ticketing, entry/exit, payment, and licence plate recognition. Each record represents **one parking event** from entry → exit.


## 🔑 **Fields**

### `id`

* **Type:** Integer (Primary Key, Auto Increment)
* **Meaning:** Unique identifier for the parking session.


### `ticket_id`

* **Type:** Integer (Foreign Key → `ticket.id`)
* **Meaning:** The ticket associated with the session (in ticket-based parking).
* **Notes:** May be `NULL` in ticketless (ANPR-only) systems.
* **Example:** Ticket `1234`.


### `entry_time`

* **Type:** Text (ISO-8601 datetime, e.g., `YYYY-MM-DDTHH:MM:SS`)
* **Meaning:** Timestamp when the vehicle entered the parking facility.


### `entry_station`

* **Type:** Integer (Foreign Key → `station.id`)
* **Meaning:** Identifies the entry station/terminal where the vehicle entered.


### `exit_time`

* **Type:** Text (ISO-8601 datetime)
* **Meaning:** Timestamp when the vehicle exited.
* **Notes:** `NULL` if the vehicle is still inside.


### `exit_station`

* **Type:** Integer (Foreign Key → `station.id`)
* **Meaning:** Identifies the exit station used by the vehicle.


### `status`

* **Type:** Text (Enum-like)
* **Meaning:** Current state of the session.
* **Values:**

  * `active` → Vehicle is inside, session ongoing.
  * `paid` → Payment completed, waiting for exit.
  * `exited` → Vehicle has exited.
  * `overdue` → Time expired / unpaid.
  * `closed` → Session finalized.


### `amount_due_cents`

* **Type:** Integer (cents)
* **Meaning:** Total fee calculated for the session, **based on tariff**.
* **Example:** `3000` = 30.00 MDL.


### `amount_paid_cents`

* **Type:** Integer (cents)
* **Meaning:** Total amount paid so far. Helps track under/overpayment.
* **Example:** `2000` = 20.00 MDL paid.


### `paid_until`

* **Type:** Text (ISO-8601 datetime)
* **Meaning:** Time until which the session is covered by payment.
* **Use case:** Useful when a driver pays before exit but leaves later.
* **Example:** `2025-09-09T13:15:00`.


### `licence_plate_entry`

* **Type:** Text
* **Meaning:** Licence plate recognized (via ANPR) at entry.
* **Example:** `ABC123`.


### `licence_plate_exit`

* **Type:** Text
* **Meaning:** Licence plate recognized at exit (may differ if ANPR misread or plate changed).
* **Example:** `A8C123`.


# ✅ Example Records

| id | ticket\_id | entry\_time         | entry\_station | exit\_time          | exit\_station | status | amount\_due\_cents | amount\_paid\_cents | paid\_until         | licence\_plate\_entry | licence\_plate\_exit |
| -- | ---------- | ------------------- | -------------- | ------------------- | ------------- | ------ | ------------------ | ------------------- | ------------------- | --------------------- | -------------------- |
| 1  | 1234       | 2025-09-09T08:15:00 | 1              | 2025-09-09T12:45:00 | 2             | exited | 3000               | 3000                | 2025-09-09T12:50:00 | ABC123                | ABC123               |
| 2  | 1235       | 2025-09-09T09:00:00 | 1              | NULL                | NULL          | active | 1500               | 0                   | NULL                | XYZ999                | NULL                 |
| 3  | NULL       | 2025-09-09T10:30:00 | 1              | NULL                | NULL          | active | 0                  | 0                   | NULL                | DEF777                | NULL                 |

---

# 📡 `event` Table Explanation

The `event` table records **all important actions or occurrences** within the parking system. It acts like a **log/audit trail**, capturing when and where something happened (e.g., ticket issued, barrier lifted, payment attempt, ANPR read).


## 🔑 **Fields**

### `id`

* **Type:** Integer (Primary Key, Auto Increment)
* **Meaning:** Unique identifier for the event record.


### `session_id`

* **Type:** Integer (Foreign Key → `session.id`)
* **Meaning:** Links the event to the **parking session** it belongs to.
* **Notes:** Can be `NULL` for system-wide events not tied to a specific session (e.g., device restart).


### `station_id`

* **Type:** Integer (Foreign Key → `station.id`)
* **Meaning:** The station (terminal, camera, intercom, etc.) where the event occurred.


### `type`

* **Type:** Text (Enum-like)
* **Meaning:** Defines the **category of event**.
* **Values:**

  * `ticket_issued` → Ticket printed at entry.
  * `anpr_read` → Licence plate captured.
  * `payment_attempt` → Customer tried to pay.
  * `payment_success` → Payment confirmed.
  * `barrier_raised` → Barrier opened.
  * `intercom_call` → Customer pressed help button.
  * `system_error` → Device or process failure.


### `occurred_at`

* **Type:** Text (ISO-8601 datetime)
* **Meaning:** Timestamp when the event took place.
* **Example:** `2025-09-09T12:46:05`.


### `payload_json`

* **Type:** Text (JSON-encoded data)
* **Meaning:** Stores additional structured details about the event, flexible for many cases.
* **Examples:**

  * For `anpr_read`: `{ "plate": "ABC123", "confidence": 0.95 }`
  * For `payment_attempt`: `{ "amount_cents": 3000, "method": "card" }`
  * For `system_error`: `{ "error_code": "E404", "message": "Barrier sensor not responding" }`


# ✅ Example Records

| id | session\_id | station\_id | type             | occurred\_at        | payload\_json                                |
| -- | ----------- | ----------- | ---------------- | ------------------- | -------------------------------------------- |
| 1  | 101         | 1           | ticket\_issued   | 2025-09-09T08:15:00 | `{ "ticket_code": "TCK-12345" }`             |
| 2  | 101         | 5           | anpr\_read       | 2025-09-09T08:15:05 | `{ "plate": "ABC123", "confidence": 0.93 }`  |
| 3  | 101         | 3           | payment\_success | 2025-09-09T12:40:00 | `{ "amount_cents": 3000, "method": "card" }` |
| 4  | 101         | 2           | barrier\_raised  | 2025-09-09T12:45:00 | `{ "trigger": "session_paid" }`              |

---

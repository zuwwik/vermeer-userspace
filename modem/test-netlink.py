#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise ModemManager's actual netlink completion/parser under ASan."""
import argparse
from pathlib import Path
import shlex
import subprocess
import tempfile


def function(source, name):
    pos = source.index(name + " (")
    start = source.rfind("\nstatic ", 0, pos) + 1
    opening = source.index("{", pos)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


PREAMBLE = r'''
#include <gio/gio.h>
#include <errno.h>
#include <linux/netlink.h>
#include <linux/rtnetlink.h>
#include <string.h>
#include <sys/socket.h>
typedef struct { GSocket *socket; GHashTable *transactions; } MMNetlink;
typedef gboolean (*MsgFunc)(GTask *, struct nlmsghdr *, GError **);
typedef struct {
    MMNetlink *self;
    guint32 sequence_id;
    GSource *timeout_source;
    GTask *completion_task;
    MsgFunc completion_fn;
} Transaction;
static guint8 packet[256];
static gsize packet_len;
#define mm_obj_warn(...) ((void)0)
static gssize receive_packet(GSocket *socket, GSocketAddress **address,
    GInputVector *vectors, gint n_vectors, GSocketControlMessage ***messages,
    gint *n_messages, gint *flags, GCancellable *cancellable, GError **error)
{
    struct sockaddr_nl sender = { .nl_family = AF_NETLINK };
    g_assert_cmpuint(vectors[0].size, >=, packet_len);
    memcpy(vectors[0].buffer, packet, packet_len);
    *address = g_socket_address_new_from_native(&sender, sizeof(sender));
    return packet_len;
}
#define g_socket_receive_message receive_packet
'''

HARNESS = r'''
static guint completions;
static gboolean completed(GTask *task, struct nlmsghdr *hdr, GError **error)
{
    ++completions;
    g_task_return_boolean(task, TRUE);
    return TRUE;
}
static void destroy_transaction(gpointer p)
{
    Transaction *tr = p;
    g_assert_null(tr->completion_task);
    g_free(tr);
}
static GTask *new_transaction(MMNetlink *self, guint seq)
{
    GTask *task = g_task_new(NULL, NULL, NULL, NULL);
    Transaction *tr = g_new0(Transaction, 1);
    tr->self = self;
    tr->sequence_id = seq;
    tr->completion_task = g_object_ref(task);
    tr->completion_fn = completed;
    g_hash_table_insert(self->transactions, GUINT_TO_POINTER(seq), tr);
    return task;
}
static void append_ack(guint seq, gint error)
{
    struct nlmsghdr *hdr = (void *)(packet + packet_len);
    struct nlmsgerr *ack;
    hdr->nlmsg_len = NLMSG_LENGTH(sizeof(*ack));
    hdr->nlmsg_type = NLMSG_ERROR;
    hdr->nlmsg_seq = seq;
    ack = NLMSG_DATA(hdr);
    ack->error = error;
    packet_len += NLMSG_ALIGN(hdr->nlmsg_len);
}
int main(void)
{
    MMNetlink self = {0};
    g_autoptr(GTask) first = NULL, second = NULL;
    g_autoptr(GError) error = NULL;
    self.transactions = g_hash_table_new_full(g_direct_hash, g_direct_equal,
                                             NULL, destroy_transaction);
    first = new_transaction(&self, 1);
    second = new_transaction(&self, 2);
    /* One receive contains a successful ACK and a rejected next request. */
    append_ack(1, 0);
    append_ack(2, -EINVAL);
    g_assert_true(netlink_messages_cb(NULL, G_IO_IN, &self));
    g_assert_cmpuint(g_hash_table_size(self.transactions), ==, 0);
    g_assert_true(g_task_propagate_boolean(first, NULL));
    g_assert_false(g_task_propagate_boolean(second, &error));
    g_assert_nonnull(error);
    g_assert_cmpuint(completions, ==, 1);
    g_hash_table_unref(self.transactions);
    g_print("PASS: freed transaction completion; batched ACKs; per-message errors\n");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="ModemManager src/mm-netlink.c")
    args = parser.parse_args()
    source = args.source.read_text()
    code = PREAMBLE + "\n".join(function(source, name) for name in (
        "transaction_complete", "netlink_messages_cb")) + HARNESS
    with tempfile.TemporaryDirectory(prefix="mm-netlink-test-") as tmp:
        src, exe = Path(tmp) / "test.c", Path(tmp) / "test"
        src.write_text(code)
        flags = shlex.split(subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "gio-2.0"], text=True))
        subprocess.run(["cc", "-g", "-O1", "-fsanitize=address,undefined",
                        "-fno-omit-frame-pointer", str(src), "-o", str(exe),
                        *flags], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()

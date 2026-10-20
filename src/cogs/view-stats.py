import os
import re
import asyncio
import discord
import logging
from discord import app_commands
from discord.ext import commands
from prettytable import PrettyTable

logger = logging.getLogger(__name__)

DISCORD_GUILD_ID = os.environ.get('DISCORD_GUILD_ID')
# Host /proc is bind-mounted here; fall back to the container's own /proc if it isn't.
PROC_ROOT = "/host_proc" if os.path.isdir("/host_proc") else "/proc"
# Host / is bind-mounted here so disk usage can be read for every host filesystem.
HOST_ROOT = "/host"

# Virtual/kernel filesystems that don't represent real disks
PSEUDO_FS_TYPES = {
    "autofs", "binfmt_misc", "bpf", "cgroup", "cgroup2", "configfs", "debugfs", "devpts", "devtmpfs",
    "efivarfs", "erofs", "fusectl", "fuse.lxcfs", "hugetlbfs", "iso9660", "mqueue", "nsfs", "overlay",
    "proc", "pstore", "ramfs", "rpc_pipefs", "securityfs", "selinuxfs", "squashfs", "sysfs", "tmpfs", "tracefs",
}
# Container runtime internals that show up as real filesystems on the host
SKIPPED_MOUNT_PREFIXES = ("/proc", "/sys", "/dev", "/run", "/var/lib/docker/", "/var/lib/containers/", "/var/lib/kubelet/")

def parse_mounts(text: str) -> list[str]:
    """Mount points of real filesystems from a /proc/<pid>/mounts table, first mount per device only."""
    seen_devices = set()
    mount_points = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        device, mount_point, fs_type = parts[0], parts[1], parts[2]
        # The kernel octal-escapes spaces, tabs, and backslashes in mount points
        mount_point = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), mount_point)
        # "/" is kept even as overlay so the container fallback still reports its root
        if mount_point != "/" and (fs_type in PSEUDO_FS_TYPES or mount_point.startswith(SKIPPED_MOUNT_PREFIXES)):
            continue
        if device in seen_devices:
            continue
        seen_devices.add(device)
        mount_points.append(mount_point)
    return mount_points

def format_bytes(num: float) -> str:
    for unit in ("B", "K", "M", "G", "T"):
        if num < 1024:
            return f"{num:.1f}{unit}"
        num /= 1024
    return f"{num:.1f}P"

class ViewStats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_meminfo(self, proc_root="/proc/meminfo"):
        meminfo = {}
        try:
            with open(f"{proc_root}", "r") as f:
                for line in f:
                    if ":" in line:
                        key, value = line.split(":", 1)
                        meminfo[key.strip()] = value.strip()
        except Exception as e:
            logger.error("Error reading meminfo: %s", e)
        return meminfo

    def get_cpu_stat(self, proc_root="/proc/stat"):
        cpu_stats = {}
        try:
            with open(f"{proc_root}", "r") as f:
                for line in f:
                    if line.startswith("cpu "):
                        parts = line.split()
                        cpu_stats = {
                            "user": int(parts[1]),
                            "nice": int(parts[2]),
                            "system": int(parts[3]),
                            "idle": int(parts[4]),
                            "iowait": int(parts[5]) if len(parts) > 5 else 0,
                            "irq": int(parts[6]) if len(parts) > 6 else 0,
                            "softirq": int(parts[7]) if len(parts) > 7 else 0,
                        }
                        break
        except Exception as e:
            logger.error("Error reading CPU stat: %s", e)
        return cpu_stats

    async def get_current_cpu_usage(self, proc_root="/proc/stat") -> float | None:
        # Get the first reading.
        stat1 = self.get_cpu_stat(proc_root)
        await asyncio.sleep(1)
        # Get the second reading.
        stat2 = self.get_cpu_stat(proc_root)
        if not stat1 or not stat2:
            return None

        # Sum up all CPU times for each reading.
        total1 = sum(stat1.get(k, 0) for k in ("user", "nice", "system", "idle", "iowait", "irq", "softirq"))
        total2 = sum(stat2.get(k, 0) for k in ("user", "nice", "system", "idle", "iowait", "irq", "softirq"))
        idle1 = stat1.get("idle", 0) + stat1.get("iowait", 0)
        idle2 = stat2.get("idle", 0) + stat2.get("iowait", 0)

        delta_total = total2 - total1
        delta_idle = idle2 - idle1

        if delta_total == 0:
            return 0.0
        # CPU usage during the interval.
        current_usage = (delta_total - delta_idle) / delta_total * 100
        return current_usage

    def get_uptime(self, proc_root="/proc/uptime"):
        try:
            with open(f"{proc_root}", "r") as f:
                uptime_info = f.read().strip().split()
                return {
                    "uptime_seconds": float(uptime_info[0]),
                    "idle_seconds": float(uptime_info[1])
                }
        except Exception as e:
            logger.error("Error reading uptime: %s", e)
            return {}

    def format_memory_usage(self, meminfo: dict) -> str:
        if "MemTotal" not in meminfo or "MemAvailable" not in meminfo:
            return "Unavailable"
        try:
            total_str = meminfo["MemTotal"].split()[0]
            avail_str = meminfo["MemAvailable"].split()[0]
            total_kb = int(total_str)
            avail_kb = int(avail_str)
            used_kb = total_kb - avail_kb
            # Convert kilobytes to gigabytes (1 GB = 1024*1024 kB)
            used_gb = used_kb / (1024 * 1024)
            total_gb = total_kb / (1024 * 1024)
            return f"{used_gb:.2f} GB / {total_gb:.2f} GB"
        except Exception as e:
            return f"Error: {e}"

    def format_uptime(self, uptime_seconds: float) -> str:
        try:
            total_seconds = int(uptime_seconds)
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{days:02d}d:{hours:02d}h:{minutes:02d}m:{seconds:02d}s"
        except Exception as e:
            return f"Error: {e}"
        
    def get_disk_usage(self) -> str:
        # Host / bind-mounted at /host pairs with the host's mount table; otherwise list the container's own mounts.
        if os.path.isdir(HOST_ROOT) and PROC_ROOT == "/host_proc":
            mounts_file, prefix = f"{PROC_ROOT}/1/mounts", HOST_ROOT
        else:
            mounts_file, prefix = "/proc/self/mounts", ""
        try:
            with open(mounts_file, "r") as f:
                mount_points = parse_mounts(f.read())
        except Exception as e:
            logger.error("Error reading mounts: %s", e)
            return f"Error retrieving disk usage: {e}"

        pt = PrettyTable(["Mounted On", "Used", "Available"])
        for mount_point in mount_points:
            path = prefix + mount_point if mount_point != "/" else (prefix or "/")
            # Skip file bind mounts (e.g. Docker's /etc/hosts) and anything we can't stat
            if not os.path.isdir(path):
                continue
            try:
                st = os.statvfs(path)
            except OSError as e:
                logger.warning("Error reading disk usage for %s: %s", mount_point, e)
                continue
            if st.f_blocks == 0:
                continue
            used = (st.f_blocks - st.f_bfree) * st.f_frsize
            available = st.f_bavail * st.f_frsize
            pt.add_row([mount_point, format_bytes(used), format_bytes(available)])
        if not pt.rows:
            return "No disk usage data available"
        return pt.get_string()

    @app_commands.command(name='view-stats', description='See system stats on host')
    @app_commands.guilds(discord.Object(id=DISCORD_GUILD_ID)) # type: ignore
    async def view_stats(self, interaction: discord.Interaction):
        proc_root_meminfo = f"{PROC_ROOT}/meminfo"
        proc_root_stat = f"{PROC_ROOT}/stat"
        proc_root_uptime = f"{PROC_ROOT}/uptime"
        meminfo = self.get_meminfo(proc_root_meminfo)
        uptime_info = self.get_uptime(proc_root_uptime)

        # Format system metrics.
        memory_usage = self.format_memory_usage(meminfo)
        current_cpu = await self.get_current_cpu_usage(proc_root_stat)
        formatted_uptime = self.format_uptime(uptime_info["uptime_seconds"]) if uptime_info else "Unavailable"

        system_data = {
            "Memory Usage": memory_usage,
            "CPU Usage": f"{current_cpu:.2f}%" if current_cpu is not None else "Unavailable",
            "Uptime": formatted_uptime
        }

        pt_sys = PrettyTable(["Metric", "Value"])
        for metric, value in system_data.items():
            pt_sys.add_row([metric, value])
        system_table_str = pt_sys.get_string()

        # statvfs can block on a dead network mount, so keep it off the event loop
        disk_usage_str = await asyncio.to_thread(self.get_disk_usage)

        system_embed = discord.Embed(
            title="System Stats",
            description=f"```plaintext\n{system_table_str}\n```",
            color=discord.Color.blue()
        )

        disk_embed = discord.Embed(
            title="Disk Usage Stats",
            description=f"```plaintext\n{disk_usage_str}\n```",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embeds=[system_embed, disk_embed], ephemeral=True, delete_after=30)

async def setup(bot: commands.Bot):
    await bot.add_cog(ViewStats(bot))

if __name__ == "__main__":
    # Self-check for the mount table parser: DISCORD_GUILD_ID=1 python3 cogs/view-stats.py
    sample = "\n".join([
        "/dev/sda1 / ext4 rw 0 0",
        "proc /proc proc rw 0 0",
        "tmpfs /run tmpfs rw 0 0",
        "/dev/sdb1 /mnt/my\\040drive xfs rw 0 0",
        "/dev/sda1 /var/lib/docker ext4 rw 0 0",
        "overlay /var/lib/docker/overlay2/abc/merged overlay rw 0 0",
        "tank/media /tank/media zfs rw 0 0",
        "nas:/share /mnt/nas nfs4 rw 0 0",
        "/dev/sdb1 /srv/bind xfs rw 0 0",
    ])
    assert parse_mounts(sample) == ["/", "/mnt/my drive", "/tank/media", "/mnt/nas"], parse_mounts(sample)
    assert parse_mounts("overlay / overlay rw 0 0") == ["/"]
    assert format_bytes(0) == "0.0B" and format_bytes(1536) == "1.5K" and format_bytes(5 * 1024**4) == "5.0T"
    print("view-stats self-check passed")

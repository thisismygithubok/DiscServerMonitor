import os
import asyncio
import json
import discord
import logging
import subprocess
from discord import app_commands
from discord.ext import commands
from prettytable import PrettyTable

logger = logging.getLogger(__name__)

DISCORD_GUILD_ID = os.environ.get('DISCORD_GUILD_ID')

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
            meminfo['error'] = f"Error reading meminfo: {e}"
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
            cpu_stats['error'] = f"Error reading CPU stat: {e}"
        return cpu_stats

    async def get_current_cpu_usage(self, proc_root="/proc/stat") -> float:
        """
        Reads /proc/stat twice (separated by 1 second) and computes the difference.
        Returns the CPU utilization over that interval.
        """
        # Get the first reading.
        stat1 = self.get_cpu_stat(proc_root)
        await asyncio.sleep(1)
        # Get the second reading.
        stat2 = self.get_cpu_stat(proc_root)

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
            return {"error": f"Error reading uptime: {e}"}

    def format_memory_usage(self, meminfo: dict) -> str:
        try:
            total_str = meminfo.get("MemTotal", "0 kB").split()[0]
            avail_str = meminfo.get("MemAvailable", "0 kB").split()[0]
            total_kb = int(total_str)
            avail_kb = int(avail_str)
            used_kb = total_kb - avail_kb
            # Convert kilobytes to gigabytes (1 GB = 1024*1024 kB)
            used_gb = used_kb / (1024 * 1024)
            total_gb = total_kb / (1024 * 1024)
            return f"{used_gb:.2f} GB / {total_gb:.2f} GB"
        except Exception as e:
            return f"Error: {e}"

    def calculate_cpu_usage(self, cpu_stats: dict) -> float:
        """
        Using cumulative CPU times from /proc/stat, calculates the average CPU usage percentage.
        Note: This is an average since boot. For an instantaneous reading,
              you would need to compare two readings over a short interval.
        """
        try:
            user = cpu_stats.get("user", 0)
            nice = cpu_stats.get("nice", 0)
            system = cpu_stats.get("system", 0)
            idle = cpu_stats.get("idle", 0)
            iowait = cpu_stats.get("iowait", 0)
            irq = cpu_stats.get("irq", 0)
            softirq = cpu_stats.get("softirq", 0)
            total = user + nice + system + idle + iowait + irq + softirq
            # Active time excludes idle and iowait.
            active = total - idle - iowait
            if total == 0:
                return 0.0
            return (active / total) * 100
        except Exception:
            return 0.0

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
        try:
            result = subprocess.run(["df", "-h"], capture_output=True, text=True, check=True)
            lines = result.stdout.strip().splitlines()
            if not lines:
                return "No disk usage data available"
            pt = PrettyTable(["Mounted On", "Used", "Available"])
            # Skip the header line and process data rows.
            for line in lines[1:]:
                row = line.strip().split(None, 5)
                if len(row) < 6:
                    continue
                mounted_on = row[5]
                used = row[2]
                available = row[3]
                pt.add_row([mounted_on, used, available])
            return pt.get_string()
        except subprocess.CalledProcessError as e:
            logger.error("Error running 'df -h': %s", e)
            return f"Error retrieving disk usage: {e}"

    @app_commands.command(name='view-stats', description='See system stats on host')
    @app_commands.guilds(discord.Object(id=DISCORD_GUILD_ID)) # type: ignore
    async def view_stats(self, interaction: discord.Interaction):
        proc_root_meminfo = "/proc/meminfo"
        proc_root_stat = "/proc/stat"
        proc_root_uptime = "/proc/uptime"
        meminfo = self.get_meminfo(proc_root_meminfo)
        cpu_stat = self.get_cpu_stat(proc_root_stat)
        uptime_info = self.get_uptime(proc_root_uptime)

        # Format system metrics.
        memory_usage = self.format_memory_usage(meminfo)
        current_cpu = await self.get_current_cpu_usage(proc_root_stat)
        formatted_uptime = self.format_uptime(uptime_info.get("uptime_seconds", 0))

        system_data = {
            "Memory Usage": memory_usage,
            "CPU Usage": f"{current_cpu:.2f}%",
            "Uptime": formatted_uptime
        }

        pt_sys = PrettyTable(["Metric", "Value"])
        for metric, value in system_data.items():
            pt_sys.add_row([metric, value])
        system_table_str = pt_sys.get_string()

        disk_usage_str = self.get_disk_usage()

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
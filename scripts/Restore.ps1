# Apply Windows default pointers. -Uninstall also removes the installed pack.
param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'
$folder = Join-Path $env:LOCALAPPDATA 'AmiyaCursorPack'
$key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Control Panel\Cursors')
try {
    # Empty values use Windows' built-in cursor for that role.
    $defaults = [ordered]@{
        Arrow='aero_arrow.cur'; Help='aero_helpsel.cur'; AppStarting='aero_working.ani'
        Wait='aero_busy.ani'; Crosshair=''; IBeam=''; NWPen='aero_pen.cur'
        No='aero_unavail.cur'; SizeNS='aero_ns.cur'; SizeWE='aero_ew.cur'
        SizeNWSE='aero_nwse.cur'; SizeNESW='aero_nesw.cur'; SizeAll='aero_move.cur'
        UpArrow='aero_up.cur'; Hand='aero_link.cur'; Pin=''; Person=''
    }
    foreach ($role in $defaults.Keys) {
        $file = $defaults[$role]
        if ($file -and -not (Test-Path -LiteralPath (Join-Path $env:SystemRoot "Cursors\$file"))) {
            throw "Windows default cursor is missing: $file. No settings were changed."
        }
    }
    foreach ($role in $defaults.Keys) {
        $file = $defaults[$role]
        $value = if ($file) { "%SystemRoot%\Cursors\$file" } else { '' }
        $key.SetValue($role, $value, [Microsoft.Win32.RegistryValueKind]::ExpandString)
    }
    # Clear the custom scheme name; Windows can display its localized default label.
    $key.SetValue('', '', [Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('Scheme Source', 0, [Microsoft.Win32.RegistryValueKind]::DWord)
    $key.Flush()
} finally {
    $key.Close()
}
if (-not ('AmiyaCursor.Win32' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace AmiyaCursor {
    public static class Win32 {
        [DllImport("user32.dll", SetLastError=true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool SystemParametersInfo(uint action, uint param, IntPtr pvParam, uint flags);
    }
}
'@
}
$refresh = [AmiyaCursor.Win32]::SystemParametersInfo(0x57, 0, [IntPtr]::Zero, 0x02)
if (-not $refresh) {
    Write-Warning 'Refresh not confirmed; apply a pointer scheme in Windows Mouse Properties.'
}
Write-Host 'Applied Windows default cursor files.'

# Remove the obsolete backup produced by earlier versions.
$legacyBackup = Join-Path $folder 'original-cursors.json'
if (Test-Path -LiteralPath $legacyBackup -PathType Leaf) {
    Remove-Item -LiteralPath $legacyBackup -Force
}

if ($Uninstall) {
    $reg = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Control Panel\Cursors\Schemes', $true)
    if ($null -ne $reg) {
        try {
            foreach ($size in @(64,96,128)) {
                $reg.DeleteValue("Amiya Chibi $size px", $false)
            }
            $reg.DeleteValue('Amiya Chibi', $false)
        } finally { $reg.Close() }
    }
    $cursorFolder = Join-Path $folder 'cursors'
    if (Test-Path -LiteralPath $cursorFolder) {
        Remove-Item -LiteralPath $cursorFolder -Recurse -Force
    }
    Write-Host 'Removed installed cursor copies and registered schemes.'
}

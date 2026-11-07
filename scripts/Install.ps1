# Per-user installer for the Amiya cursor scheme.
# Does not require administrator access or modify System32.
$ErrorActionPreference = 'Stop'

$packRoot = Split-Path -Parent $PSScriptRoot
$destinationRoot = Join-Path $env:LOCALAPPDATA 'AmiyaCursorPack'
$roles = @('Arrow','Help','AppStarting','Wait','Crosshair','IBeam','NWPen','No','SizeNS','SizeWE','SizeNWSE','SizeNESW','SizeAll','UpArrow','Hand','Pin','Person')
$names = @('arrow.cur','help.cur','appstarting.ani','wait.ani','crosshair.cur','ibeam.cur','nwpen.cur','no.cur','sizens.cur','sizewe.cur','sizenwse.cur','sizenesw.cur','sizeall.cur','uparrow.cur','hand.cur','pin.cur','person.cur')

if ($roles.Count -ne $names.Count) { throw 'Registry role mapping mismatch.' }
New-Item -ItemType Directory -Force -Path $destinationRoot | Out-Null

# Copy the multi-resolution files to a stable folder.
    $src = Join-Path $packRoot 'cursors\multi'
    $dst = Join-Path $destinationRoot 'cursors\multi'
    if (-not (Test-Path $src)) { throw "Missing source cursor folder: $src" }
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    Copy-Item -Path (Join-Path $src '*.cur') -Destination $dst -Force
    Copy-Item -Path (Join-Path $src '*.ani') -Destination $dst -Force
    foreach ($name in $names) {
        if (-not (Test-Path (Join-Path $dst $name))) { throw "Missing cursor: $name" }
    }

$key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Control Panel\Cursors')
if ($null -eq $key) { throw 'Cannot open user cursor registry key.' }
try {
    $dir = Join-Path $destinationRoot 'cursors\multi'
    $paths = @()
    for ($i = 0; $i -lt $roles.Count; $i++) {
        $path = Join-Path $dir $names[$i]
        $key.SetValue($roles[$i], $path, [Microsoft.Win32.RegistryValueKind]::ExpandString)
        $paths += $path
    }
    $schemeTitle = 'Amiya Chibi'
    $key.SetValue('', $schemeTitle, [Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('Scheme Source', 2, [Microsoft.Win32.RegistryValueKind]::DWord)
    $key.Flush()

    $schemeKey = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Control Panel\Cursors\Schemes')
    try {
        $schemeKey.SetValue($schemeTitle, ($paths -join ','), [Microsoft.Win32.RegistryValueKind]::ExpandString)
        $schemeKey.Flush()
    } finally {
        $schemeKey.Close()
    }
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
Write-Host 'Installed and registered: Amiya Chibi'
if (-not $refresh) {
    Write-Warning 'Windows did not confirm live refresh. Open Mouse Properties > Pointers, choose the Amiya scheme, and Apply.'
}
Write-Host 'Open pointer settings: control.exe main.cpl,,1'

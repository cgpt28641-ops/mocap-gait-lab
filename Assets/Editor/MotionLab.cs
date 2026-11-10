// Motion Lab - headless render test.
// Step 1: one capsule -> one PNG, plus info about the graphics device.
using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class MotionLab
{
    const string OutDir = "build/render";

    // Called from CI: -executeMethod MotionLab.RenderTest
    public static void RenderTest()
    {
        Directory.CreateDirectory(OutDir);
        string info =
            "unity=" + Application.unityVersion + "\n" +
            "gfx=" + SystemInfo.graphicsDeviceType + "\n" +
            "gfxName=" + SystemInfo.graphicsDeviceName + "\n" +
            "gfxVersion=" + SystemInfo.graphicsDeviceVersion + "\n" +
            "time=" + DateTime.UtcNow.ToString("o") + "\n";
        File.WriteAllText(Path.Combine(OutDir, "info.txt"), info);
        Debug.Log("[MotionLab] " + info.Replace("\n", " | "));

        if (SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null)
        {
            Debug.LogError("[MotionLab] No graphics device (running with -nographics?). Cannot render.");
            EditorApplication.Exit(2);
            return;
        }

        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        var lightGo = new GameObject("Sun");
        var light = lightGo.AddComponent<Light>();
        light.type = LightType.Directional;
        light.intensity = 1.2f;
        lightGo.transform.rotation = Quaternion.Euler(50f, -30f, 0f);

        var floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
        floor.transform.localScale = new Vector3(0.5f, 1f, 0.5f);
        SetColor(floor, new Color(0.55f, 0.58f, 0.62f));

        var capsule = GameObject.CreatePrimitive(PrimitiveType.Capsule);
        capsule.transform.position = new Vector3(0f, 1f, 0f);
        SetColor(capsule, new Color(0.85f, 0.45f, 0.2f));

        var camGo = new GameObject("Cam");
        var cam = camGo.AddComponent<Camera>();
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color(0.12f, 0.14f, 0.18f);
        cam.fieldOfView = 35f;
        camGo.transform.position = new Vector3(2.5f, 1.8f, -4f);
        camGo.transform.LookAt(new Vector3(0f, 0.9f, 0f));

        SavePng(cam, Path.Combine(OutDir, "capsule.png"), 512, 512);
        Debug.Log("[MotionLab] Done.");
    }

    static void SetColor(GameObject go, Color c)
    {
        var r = go.GetComponent<Renderer>();
        var mat = new Material(Shader.Find("Standard"));
        mat.color = c;
        r.sharedMaterial = mat;
    }

    static void SavePng(Camera cam, string path, int w, int h)
    {
        var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32);
        rt.antiAliasing = 4;
        cam.targetTexture = rt;
        cam.Render();
        var prev = RenderTexture.active;
        RenderTexture.active = rt;
        var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
        tex.Apply();
        RenderTexture.active = prev;
        cam.targetTexture = null;
        File.WriteAllBytes(path, tex.EncodeToPNG());
        UnityEngine.Object.DestroyImmediate(tex);
        rt.Release();
        Debug.Log("[MotionLab] Wrote " + path);
    }
}

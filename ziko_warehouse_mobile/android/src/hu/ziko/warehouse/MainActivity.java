package hu.ziko.warehouse;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.ClipData;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.os.SystemClock;
import android.provider.MediaStore;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.SslErrorHandler;
import android.net.http.SslError;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;
import org.json.JSONObject;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;

/** Native display shell. Warehouse data, auth, and 2126 UI stay on the server. */
public final class MainActivity extends Activity {
    private static final String PREFS="ziko.warehouse.mobile";
    private static final String DEFAULT_SERVER="http://192.168.10.74:8788";
    private static final int SELECT_MEDIA=81;
    private final int dark=Color.rgb(8,16,28), teal=Color.rgb(103,235,211);
    private WebView web;
    private ProgressBar loading;
    private TextView status;
    private FrameLayout content;
    private View offline;
    private Uri pendingPhoto;
    private ValueCallback<Uri[]> chooserCallback;
    private String server;
    private long lastBackground, lastHealth;
    private boolean failedMain;

    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        getWindow().setStatusBarColor(dark);
        getWindow().setNavigationBarColor(dark);
        server=getPreferences(MODE_PRIVATE).getString("endpoint",DEFAULT_SERVER);
        if(!validEndpoint(server))server=DEFAULT_SERVER;
        createLayout();
        configureBrowser();
        if(state!=null)web.restoreState(state);else openServer();
        probeHealth();
    }

    private int dp(float number){return Math.round(number*getResources().getDisplayMetrics().density);}
    private GradientDrawable bg(int fill,int border,int radius){
        GradientDrawable drawable=new GradientDrawable();
        drawable.setColor(fill);drawable.setCornerRadius(dp(radius));
        if(border!=Color.TRANSPARENT)drawable.setStroke(dp(1),border);
        return drawable;
    }
    private TextView label(String text,int size,int color,boolean bold){
        TextView out=new TextView(this);
        out.setText(text);out.setTextColor(color);out.setTextSize(size);
        out.setGravity(Gravity.CENTER_VERTICAL);
        if(bold)out.setTypeface(null,Typeface.BOLD);
        return out;
    }
    private Button toolbarButton(String title){
        Button btn=new Button(this);
        btn.setText(title);btn.setAllCaps(false);btn.setTextSize(18);
        btn.setTextColor(teal);
        btn.setPadding(dp(10),0,dp(10),0);
        btn.setBackground(bg(Color.rgb(20,43,56),Color.rgb(42,100,107),13));
        btn.setMinHeight(dp(46));btn.setMinWidth(dp(48));
        return btn;
    }
    private void createLayout(){
        LinearLayout root=new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(dark);
        LinearLayout header=new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);header.setPadding(dp(12),dp(6),dp(12),dp(6));
        header.setBackgroundColor(Color.rgb(14,28,42));
        TextView mark=label("▣",28,teal,true);mark.setGravity(Gravity.CENTER);
        mark.setBackground(bg(Color.rgb(24,65,73),Color.rgb(56,146,141),12));
        header.addView(mark,new LinearLayout.LayoutParams(dp(45),dp(45)));
        LinearLayout headings=new LinearLayout(this);
        headings.setPadding(dp(11),0,dp(8),0);
        headings.setOrientation(LinearLayout.VERTICAL);
        headings.addView(label("ZIKO · Warehouse",16,Color.WHITE,true));
        status=label("Kapcsolódás…",11,Color.rgb(147,180,192),false);
        headings.addView(status);
        header.addView(headings,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        Button refresh=toolbarButton("⟳");
        refresh.setContentDescription("Frissítés");
        refresh.setOnClickListener(v->refresh(true));
        header.addView(refresh,new LinearLayout.LayoutParams(dp(48),dp(46)));
        Button settings=toolbarButton("⚙");
        settings.setContentDescription("Warehouse szerver beállítása");
        LinearLayout.LayoutParams settingsLp=new LinearLayout.LayoutParams(dp(48),dp(46));settingsLp.leftMargin=dp(7);
        settings.setOnClickListener(v->settingsDialog());
        header.addView(settings,settingsLp);
        root.addView(header,new LinearLayout.LayoutParams(-1,dp(60)));
        loading=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);
        loading.setMax(100);loading.setProgressTintList(android.content.res.ColorStateList.valueOf(teal));
        root.addView(loading,new LinearLayout.LayoutParams(-1,dp(3)));
        content=new FrameLayout(this);
        web=new WebView(this);
        web.setBackgroundColor(dark);
        content.addView(web,new FrameLayout.LayoutParams(-1,-1));
        offline=createOfflinePanel();
        offline.setVisibility(View.GONE);
        content.addView(offline,new FrameLayout.LayoutParams(-1,-1));
        root.addView(content,new LinearLayout.LayoutParams(-1,0,1));
        setContentView(root);
    }
    private View createOfflinePanel(){
        LinearLayout pane=new LinearLayout(this);
        pane.setGravity(Gravity.CENTER);
        pane.setOrientation(LinearLayout.VERTICAL);
        pane.setPadding(dp(24),dp(24),dp(24),dp(24));
        pane.setBackgroundColor(dark);
        TextView symbol=label("⌁",54,teal,true);symbol.setGravity(Gravity.CENTER);
        pane.addView(symbol);
        TextView title=label("Nem érhető el a Warehouse",22,Color.WHITE,true);
        title.setGravity(Gravity.CENTER);pane.addView(title);
        TextView note=label("Ellenőrizd a saját Wi-Fi / VPN kapcsolatot, majd próbáld újra.",14,Color.rgb(161,191,201),false);
        note.setGravity(Gravity.CENTER);note.setPadding(0,dp(14),0,dp(22));pane.addView(note);
        Button retry=toolbarButton("⟳  Újrapróbálás");retry.setTextSize(16);
        retry.setOnClickListener(v->refresh(true));
        pane.addView(retry,new LinearLayout.LayoutParams(-1,dp(54)));
        Button change=toolbarButton("⚙  Szerver címe");change.setTextSize(15);
        change.setOnClickListener(v->settingsDialog());
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(50));lp.topMargin=dp(12);pane.addView(change,lp);
        return pane;
    }
    private void configureBrowser(){
        WebSettings opts=web.getSettings();
        opts.setJavaScriptEnabled(true);
        opts.setDomStorageEnabled(true);
        opts.setSupportZoom(false);
        opts.setBuiltInZoomControls(false);
        opts.setAllowFileAccess(false);
        opts.setAllowContentAccess(true); // User-selected system photo picker URIs
        opts.setAllowFileAccessFromFileURLs(false);
        opts.setAllowUniversalAccessFromFileURLs(false);
        opts.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        opts.setCacheMode(WebSettings.LOAD_DEFAULT);
        opts.setMediaPlaybackRequiresUserGesture(true);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
        WebView.setWebContentsDebuggingEnabled(false);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                if(!allowed(request.getUrl())){Toast.makeText(MainActivity.this,"Csak a beállított Warehouse szerver engedélyezett.",Toast.LENGTH_SHORT).show();return true;}
                return false;
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
                Uri u=request.getUrl();
                String scheme=u.getScheme()==null?"":u.getScheme().toLowerCase(Locale.ROOT);
                if(("http".equals(scheme)||"https".equals(scheme))&&!allowed(u)){
                    return new WebResourceResponse("text/plain","UTF-8",403,"Forbidden",
                        java.util.Collections.emptyMap(),new ByteArrayInputStream(new byte[0]));
                }
                return super.shouldInterceptRequest(view,request);
            }
            @Override public void onPageStarted(WebView view,String url,android.graphics.Bitmap favicon){
                failedMain=false;offline.setVisibility(View.GONE);
                status.setText("Betöltés…");loading.setVisibility(View.VISIBLE);
            }
            @Override public void onPageFinished(WebView view,String url){
                loading.setVisibility(View.GONE);
                if(!failedMain){offline.setVisibility(View.GONE);probeHealth();}
            }
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){
                if(request.isForMainFrame())failMain();
            }
            @Override public void onReceivedHttpError(WebView view,WebResourceRequest request,WebResourceResponse response){
                if(request.isForMainFrame()&&response.getStatusCode()>=400)failMain();
            }
            @Override public void onReceivedSslError(WebView view,SslErrorHandler handler,SslError error){
                handler.cancel();failMain();
                Toast.makeText(MainActivity.this,"Érvénytelen HTTPS tanúsítvány. Nem lépek tovább.",Toast.LENGTH_LONG).show();
            }
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public void onProgressChanged(WebView view,int percent){loading.setProgress(percent);}
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(chooserCallback!=null)chooserCallback.onReceiveValue(null);
                chooserCallback=callback;
                openPhotoChooser(params);
                return true;
            }
            @Override public void onPermissionRequest(android.webkit.PermissionRequest request){
                // HTML5 getUserMedia is not needed; use system camera/file chooser instead.
                request.deny();
            }
        });
        web.setDownloadListener((url,userAgent,contentDisposition,mimeType,contentLength)->{
            Uri link=Uri.parse(url);
            if(!allowed(link)){Toast.makeText(this,"Nem engedélyezett letöltési cím.",Toast.LENGTH_LONG).show();return;}
            try{
                DownloadManager.Request req=new DownloadManager.Request(link);
                req.setMimeType(mimeType);
                req.addRequestHeader("Cookie",CookieManager.getInstance().getCookie(url)==null?"":CookieManager.getInstance().getCookie(url));
                req.setTitle("ZIKO Warehouse export");
                req.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                String file="warehouse-export-"+System.currentTimeMillis()+".csv";
                req.setDestinationInExternalFilesDir(this,Environment.DIRECTORY_DOWNLOADS,file);
                ((DownloadManager)getSystemService(DOWNLOAD_SERVICE)).enqueue(req);
                Toast.makeText(this,"Warehouse export elindítva.",Toast.LENGTH_SHORT).show();
            }catch(Exception ex){Toast.makeText(this,"Letöltés sikertelen.",Toast.LENGTH_LONG).show();}
        });
        final float[] startY={0};final boolean[] atTop={false};
        web.setOnTouchListener((v,event)->{
            if(event.getActionMasked()==MotionEvent.ACTION_DOWN){startY[0]=event.getY();atTop[0]=web.getScrollY()==0;}
            if(event.getActionMasked()==MotionEvent.ACTION_UP&&atTop[0]&&event.getY()-startY[0]>dp(130)){refresh(true);return true;}
            return false;
        });
    }
    private void failMain(){failedMain=true;offline.setVisibility(View.VISIBLE);status.setText("Nincs kapcsolat");loading.setVisibility(View.GONE);}
    private boolean allowed(Uri url){
        Uri fixed=Uri.parse(server);
        return url!=null&&url.getScheme()!=null&&url.getHost()!=null
          &&url.getScheme().equalsIgnoreCase(fixed.getScheme())
          &&url.getHost().equalsIgnoreCase(fixed.getHost())
          &&url.getPort()==fixed.getPort();
    }
    private static boolean isPrivateHost(String host){
        if(host==null)return false;
        host=host.toLowerCase(Locale.ROOT);
        if(host.endsWith(".local")||host.indexOf('.')<0)return true;
        String[] p=host.split("\\.");
        if(p.length!=4)return false;
        int[] v=new int[4];
        try{for(int i=0;i<4;i++){v[i]=Integer.parseInt(p[i]);if(v[i]<0||v[i]>255)return false;}}
        catch(NumberFormatException ex){return false;}
        return v[0]==10||(v[0]==172&&v[1]>=16&&v[1]<=31)
          ||(v[0]==192&&v[1]==168)||(v[0]==100&&v[1]>=64&&v[1]<=127);
    }
    private static boolean validEndpoint(String value){
        try{
            Uri u=Uri.parse(value.trim());
            String protocol=u.getScheme()==null?"":u.getScheme().toLowerCase(Locale.ROOT);
            if(!"http".equals(protocol)&&!"https".equals(protocol))return false;
            if(u.getHost()==null||u.getHost().isEmpty()||u.getUserInfo()!=null)return false;
            if(u.getQuery()!=null||u.getFragment()!=null)return false;
            if(u.getPath()!=null&&!u.getPath().isEmpty()&&!"/".equals(u.getPath()))return false;
            return "https".equals(protocol)||isPrivateHost(u.getHost());
        }catch(Exception ex){return false;}
    }
    private void settingsDialog(){
        EditText input=new EditText(this);
        input.setSingleLine(true);
        input.setText(server);
        input.setSelectAllOnFocus(true);
        input.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);
        LinearLayout wrap=new LinearLayout(this);wrap.setPadding(dp(23),dp(6),dp(23),0);wrap.addView(input,new LinearLayout.LayoutParams(-1,-2));
        AlertDialog dialog=new AlertDialog.Builder(this)
          .setTitle("Warehouse szerver")
          .setMessage("Saját HTTPS cím vagy privát Wi-Fi/VPN-cím. A jelszót az app nem tárolja.")
          .setView(wrap)
          .setNegativeButton("Mégse",null)
          .setPositiveButton("Mentés",null).create();
        dialog.setOnShowListener(ignored->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            String candidate=input.getText().toString().trim();
            if(!validEndpoint(candidate)){input.setError("HTTPS vagy privát helyi HTTP-cím szükséges.");return;}
            if(!candidate.equals(server)){
                server=candidate;
                getPreferences(MODE_PRIVATE).edit().putString("endpoint",server).apply();
                openServer();
            }
            dialog.dismiss();
        }));
        dialog.show();
    }
    private void openServer(){failedMain=false;offline.setVisibility(View.GONE);web.loadUrl(server);probeHealth();}
    private void refresh(boolean force){
        failedMain=false;offline.setVisibility(View.GONE);
        if(force)web.clearCache(false);
        web.reload();probeHealth();
    }
    private void probeHealth(){
        long now=SystemClock.elapsedRealtime();
        if(now-lastHealth<1500)return;
        lastHealth=now;
        String url=server+"/health";
        new Thread(()->{
            HttpURLConnection conn=null;
            try{
                conn=(HttpURLConnection)new URL(url).openConnection();
                conn.setConnectTimeout(3500);conn.setReadTimeout(3500);
                conn.setInstanceFollowRedirects(false);
                if(conn.getResponseCode()!=200)throw new Exception("health response");
                byte[] data;
                try(InputStream in=conn.getInputStream()){
                    java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();
                    byte[] buffer=new byte[512];int n,total=0;
                    while((n=in.read(buffer))!=-1&&total<2048){
                        int safe=Math.min(n,2048-total);out.write(buffer,0,safe);total+=safe;
                    }
                    data=out.toByteArray();
                }
                JSONObject health=new JSONObject(new String(data,java.nio.charset.StandardCharsets.UTF_8));
                if(!"ok".equals(health.optString("status")))throw new Exception("health status");
                String version=health.optString("version","LIVE");
                runOnUiThread(()->{if(!failedMain)status.setText("● ONLINE  ·  "+version);});
            }catch(Exception ignored){runOnUiThread(()->{if(!failedMain)status.setText("Kapcsolat ellenőrizendő");});}
            finally{if(conn!=null)conn.disconnect();}
        },"WarehouseHealth").start();
    }
    private void openPhotoChooser(WebChromeClient.FileChooserParams params){
        Intent gallery=new Intent(Intent.ACTION_GET_CONTENT);
        gallery.addCategory(Intent.CATEGORY_OPENABLE);
        gallery.setType("image/*");
        gallery.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE);
        Intent chooser=Intent.createChooser(gallery,"Warehouse fotó kiválasztása");
        try{
            ContentValues values=new ContentValues();
            values.put(MediaStore.Images.Media.DISPLAY_NAME,"ziko-warehouse-"+System.currentTimeMillis()+".jpg");
            values.put(MediaStore.Images.Media.MIME_TYPE,"image/jpeg");
            values.put(MediaStore.Images.Media.RELATIVE_PATH,Environment.DIRECTORY_PICTURES+"/ZIKO Warehouse");
            pendingPhoto=getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI,values);
            if(pendingPhoto!=null){
                Intent camera=new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
                camera.putExtra(MediaStore.EXTRA_OUTPUT,pendingPhoto);
                camera.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                camera.setClipData(ClipData.newRawUri("Warehouse kép",pendingPhoto));
                chooser.putExtra(Intent.EXTRA_INITIAL_INTENTS,new Intent[]{camera});
            }
        }catch(Exception ex){pendingPhoto=null;}
        try{startActivityForResult(chooser,SELECT_MEDIA);}
        catch(Exception ex){
            if(chooserCallback!=null){chooserCallback.onReceiveValue(null);chooserCallback=null;}
            discardPhoto();Toast.makeText(this,"Nincs elérhető fotóválasztó.",Toast.LENGTH_SHORT).show();
        }
    }
    private void discardPhoto(){
        if(pendingPhoto!=null){
            try{getContentResolver().delete(pendingPhoto,null,null);}catch(Exception ignored){}
            pendingPhoto=null;
        }
    }
    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode!=SELECT_MEDIA)return;
        Uri[] result=null;boolean wasCamera=false;
        if(resultCode==RESULT_OK){
            if(data!=null&&data.getClipData()!=null){
                ClipData clip=data.getClipData();result=new Uri[clip.getItemCount()];
                for(int i=0;i<result.length;i++)result[i]=clip.getItemAt(i).getUri();
            }else if(data!=null&&data.getData()!=null)result=new Uri[]{data.getData()};
            else if(pendingPhoto!=null){result=new Uri[]{pendingPhoto};wasCamera=true;}
        }
        if(!wasCamera)discardPhoto();else pendingPhoto=null;
        if(chooserCallback!=null){chooserCallback.onReceiveValue(result);chooserCallback=null;}
    }
    @Override protected void onPause(){lastBackground=SystemClock.elapsedRealtime();super.onPause();}
    @Override protected void onResume(){
        super.onResume();
        if(web!=null&&lastBackground>0&&SystemClock.elapsedRealtime()-lastBackground>90000){refresh(false);}
    }
    @Override public void onBackPressed(){
        if(web!=null&&web.canGoBack())web.goBack();else super.onBackPressed();
    }
    @Override protected void onSaveInstanceState(Bundle state){if(web!=null)web.saveState(state);super.onSaveInstanceState(state);}
    @Override protected void onDestroy(){
        if(chooserCallback!=null){chooserCallback.onReceiveValue(null);chooserCallback=null;}
        discardPhoto();if(web!=null){web.destroy();}
        super.onDestroy();
    }
}


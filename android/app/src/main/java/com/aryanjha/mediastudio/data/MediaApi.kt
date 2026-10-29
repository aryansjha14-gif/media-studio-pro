package com.aryanjha.mediastudio.data

import okhttp3.MultipartBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.PUT
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

interface MediaApi {

    // -- media ------------------------------------------------------------ //
    @Multipart
    @POST("v1/media")
    suspend fun upload(@Part file: MultipartBody.Part): MediaAsset

    @GET("v1/media/{id}")
    suspend fun asset(@Path("id") id: String): MediaAsset

    // -- images ----------------------------------------------------------- //
    @POST("v1/images/{id}/adjust")
    suspend fun adjust(@Path("id") id: String, @Body body: AdjustRequest): MediaAsset

    @POST("v1/images/{id}/prompt")
    suspend fun promptEdit(@Path("id") id: String, @Body body: PromptEditRequest): Job

    @POST("v1/images/generate")
    suspend fun generateImage(@Body body: GenerateImageRequest): Job

    @POST("v1/images/{id}/upscale")
    suspend fun upscale(@Path("id") id: String, @Query("factor") factor: Float = 2f): Job

    @POST("v1/images/{id}/remove-background")
    suspend fun removeBackground(@Path("id") id: String): Job

    // -- video ------------------------------------------------------------ //
    @POST("v1/videos/{id}/trim")
    suspend fun trim(@Path("id") id: String, @Body body: TrimRequest): MediaAsset

    @POST("v1/videos/{id}/frame")
    suspend fun frame(@Path("id") id: String, @Body body: FrameRequest): MediaAsset

    @POST("v1/videos/{id}/prompt")
    suspend fun videoPrompt(@Path("id") id: String, @Body body: VideoPromptRequest): Job

    @POST("v1/videos/generate")
    suspend fun generateVideo(@Body body: GenerateVideoRequest): Job

    // -- jobs ------------------------------------------------------------- //
    @GET("v1/jobs/{id}")
    suspend fun job(@Path("id") id: String): Job

    @GET("health")
    suspend fun health(): HealthResponse

    // -- v2: resumable upload for very large files ----------------------- //
    @POST("v1/uploads")
    suspend fun uploadInit(@Body body: UploadInitRequest): UploadSessionOut

    @PUT("v1/uploads/{id}")
    suspend fun uploadChunk(
        @Path("id") id: String,
        @Query("offset") offset: Long,
        @Body chunk: okhttp3.RequestBody,
    ): UploadSessionOut

    @GET("v1/uploads/{id}")
    suspend fun uploadStatus(@Path("id") id: String): UploadSessionOut

    @POST("v1/uploads/{id}/complete")
    suspend fun uploadComplete(@Path("id") id: String): MediaAsset

    // -- v2: prompt-driven auto edit ------------------------------------- //
    @POST("v1/auto/plan")
    suspend fun autoPlan(@Body body: PlanRequest): AutoPlan

    @POST("v1/auto/render")
    suspend fun autoRender(@Body body: RenderRequest): Job

    // -- v2: feature coverage -------------------------------------------- //
    @GET("v1/features/summary")
    suspend fun featureSummary(): FeatureSummary

    // -- v4: creator packs, lenses, search ------------------------------- //
    @GET("v1/platforms")
    suspend fun platforms(): List<PlatformPreset>

    @GET("v1/lenses")
    suspend fun lenses(): List<LensInfo>

    @GET("v1/features/search")
    suspend fun searchFeatures(@Query("q") query: String, @Query("limit") limit: Int = 30): List<FeatureItem>

    @POST("v1/platforms/{name}/image/{id}")
    suspend fun fitPlatformImage(
        @Path("name") name: String,
        @Path("id") id: String,
    ): MediaAsset

    @POST("v1/platforms/{name}/video/{id}")
    suspend fun fitPlatformVideo(
        @Path("name") name: String,
        @Path("id") id: String,
    ): Job

    @POST("v1/lenses/{lens}/image/{id}")
    suspend fun applyLensImage(
        @Path("lens") lens: String,
        @Path("id") id: String,
        @Query("intensity") intensity: Float = 1f,
    ): MediaAsset

    @POST("v1/lenses/{lens}/video/{id}")
    suspend fun applyLensVideo(
        @Path("lens") lens: String,
        @Path("id") id: String,
    ): Job

    @POST("v1/sticker/{id}")
    suspend fun addSticker(@Path("id") id: String, @Body body: StickerRequest): MediaAsset
}
